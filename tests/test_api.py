import pytest
from fastapi.testclient import TestClient
import api
from core.repository import TransactionRepository
from core.payment_registry import PaymentRegistry
from core.webhook import WebhookProcessor
from core.idempotency import IdempotencyStore
from tests.fake_gateway import FakeGateway
from core.database import Database
from tests.webhook_helpers import TEST_SECRET,post_signed_webhook


@pytest.fixture
def client(monkeypatch):
    # Fresh in-memory storage and a gateway that always succeeds, so tests
    # don't touch transactions.db and aren't random
    # All components share ONE in-memory Database, like in production, so
    # the atomic db.transaction() blocks in api.py work
    db=Database(":memory:")
    monkeypatch.setattr(api,"db",db)
    monkeypatch.setattr(api,"repository",TransactionRepository(db=db))
    monkeypatch.setattr(api,"payment_registry",PaymentRegistry(db=db))
    monkeypatch.setattr(api,"webhook_processor",WebhookProcessor(db=db))
    monkeypatch.setattr(api,"idempotency_store",IdempotencyStore(db=db))
    monkeypatch.setattr(api, "webhook_secret", TEST_SECRET)
    monkeypatch.setattr(api,"gateways",[FakeGateway(name="Fake",healthy=True,payment_results=[True])])
    return TestClient(api.app)


def test_create_transaction_requires_idempotency_key(client):
    response=client.post("/transactions",json={"amount":1000,"currency":"EUR"})
    assert response.status_code==400


def test_same_idempotency_key_returns_same_transaction_and_charges_once(client):
    headers={"Idempotency-Key":"key-1"}
    first=client.post("/transactions",json={"amount":1000,"currency":"EUR"},headers=headers)
    second=client.post("/transactions",json={"amount":1000,"currency":"EUR"},headers=headers)

    assert first.status_code==200
    assert second.status_code==200
    assert first.json()["transaction_id"]==second.json()["transaction_id"]
    assert api.gateways[0].call_count==1


def test_same_key_with_different_body_is_rejected(client):
    headers={"Idempotency-Key":"key-2"}
    client.post("/transactions",json={"amount":1000,"currency":"EUR"},headers=headers)
    response=client.post("/transactions",json={"amount":2000,"currency":"EUR"},headers=headers)
    assert response.status_code==422


def test_different_keys_create_different_transactions(client):
    first=client.post("/transactions",json={"amount":1000,"currency":"EUR"},headers={"Idempotency-Key":"a"})
    second=client.post("/transactions",json={"amount":1000,"currency":"EUR"},headers={"Idempotency-Key":"b"})
    assert first.json()["transaction_id"]!=second.json()["transaction_id"]


@pytest.mark.parametrize("body",[
    {"amount":10.5,"currency":"EUR"},
    {"amount":"1000","currency":"EUR"},
    {"amount":0,"currency":"EUR"},
    {"amount":-5,"currency":"EUR"},
    {"amount":1000,"currency":"LEU"},
])
def test_invalid_amount_or_currency_is_rejected(client,body):
    response=client.post("/transactions",json=body,headers={"Idempotency-Key":"k"})
    assert response.status_code==422


def test_get_unknown_transaction_returns_404(client):
    assert client.get("/transactions/does-not-exist").status_code==404

def create_processing_transaction(client,key="k",amount=1000):
    response=client.post("/transactions",json={"amount":amount,"currency":"EUR"},headers={"Idempotency-Key":key})
    assert response.json()["status"]=="PROCESSING"
    return response.json()["transaction_id"]


def webhook(client,transaction_id,webhook_id="wh_1",amount=1000,status="succeeded"):
    return post_signed_webhook(client,{
        "webhook_id":webhook_id,
        "transaction_id":transaction_id,
        "amount":amount,
        "status":status
    })

def test_get_existing_transaction_returns_its_data(client):
    transaction_id=create_processing_transaction(client)

    response=client.get(f"/transactions/{transaction_id}")

    assert response.status_code==200
    body=response.json()
    assert body["transaction_id"]==transaction_id
    assert body["amount"]==1000
    assert body["currency"]=="EUR"
    assert body["status"]=="PROCESSING"


def test_succeeded_webhook_accepts_transaction_and_persists_it(client):
    transaction_id=create_processing_transaction(client)

    response=webhook(client,transaction_id)

    assert response.status_code==200
    assert response.json()=={"processed":True,"status":"ACCEPTED"}
    assert client.get(f"/transactions/{transaction_id}").json()["status"]=="ACCEPTED"


def test_failed_webhook_rejects_transaction(client):
    transaction_id=create_processing_transaction(client)

    response=webhook(client,transaction_id,status="failed")

    assert response.json()=={"processed":True,"status":"REJECTED"}


def test_duplicate_webhook_is_ignored(client):
    transaction_id=create_processing_transaction(client)
    webhook(client,transaction_id,webhook_id="wh_dup")

    second=webhook(client,transaction_id,webhook_id="wh_dup")

    assert second.json()=={"processed":False,"status":"ACCEPTED"}


def test_webhook_with_wrong_amount_is_not_applied(client):
    transaction_id=create_processing_transaction(client)

    response=webhook(client,transaction_id,amount=999)

    assert response.json()=={"processed":False,"status":"PROCESSING"}
    assert client.get(f"/transactions/{transaction_id}").json()["status"]=="PROCESSING"


def test_webhook_for_unknown_transaction_returns_404(client):
    assert webhook(client,"does-not-exist").status_code==404


def test_webhook_with_unknown_status_returns_422(client):
    transaction_id=create_processing_transaction(client)

    assert webhook(client,transaction_id,status="refunded").status_code==422


def test_redundant_webhook_with_new_id_is_accepted_without_changes(client):
    transaction_id=create_processing_transaction(client)
    webhook(client,transaction_id,webhook_id="wh_a")

    response=webhook(client,transaction_id,webhook_id="wh_b")

    assert response.json()=={"processed":True,"status":"ACCEPTED"}


def test_contradicting_webhook_does_not_change_terminal_state(client):
    transaction_id=create_processing_transaction(client)
    webhook(client,transaction_id,webhook_id="wh_a",status="succeeded")

    response=webhook(client,transaction_id,webhook_id="wh_b",status="failed")

    assert response.json()=={"processed":False,"status":"ACCEPTED"}