import pytest
from fastapi.testclient import TestClient
import api
from core.repository import TransactionRepository
from core.payment_registry import PaymentRegistry
from core.webhook import WebhookProcessor
from core.idempotency import IdempotencyStore
from tests.fake_gateway import FakeGateway


@pytest.fixture
def client(monkeypatch):
    # Fresh in-memory storage and a gateway that always succeeds, so tests
    # don't touch transactions.db and aren't random
    monkeypatch.setattr(api,"repository",TransactionRepository(db_path=":memory:"))
    monkeypatch.setattr(api,"payment_registry",PaymentRegistry(db_path=":memory:"))
    monkeypatch.setattr(api,"webhook_processor",WebhookProcessor(db_path=":memory:"))
    monkeypatch.setattr(api,"idempotency_store",IdempotencyStore(db_path=":memory:"))
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