import json
import pytest
from fastapi.testclient import TestClient
import api
from core.database import Database
from core.repository import TransactionRepository
from core.payment_registry import PaymentRegistry
from core.webhook import WebhookProcessor
from core.idempotency import IdempotencyStore
from core.webhook_security import sign_payload, verify_signature
from tests.fake_gateway import FakeGateway
from tests.webhook_helpers import TEST_SECRET, post_signed_webhook


# ---- the signing functions on their own

def test_valid_signature_is_accepted():
    body = b'{"webhook_id":"wh_1"}'
    assert verify_signature("secret", body, sign_payload("secret", body)) is True


def test_signature_of_a_modified_body_is_rejected():
    signature = sign_payload("secret", b'{"amount":1000}')
    assert verify_signature("secret", b'{"amount":1}', signature) is False


def test_signature_made_with_another_secret_is_rejected():
    body = b'{"amount":1000}'
    assert verify_signature("secret", body, sign_payload("other-secret", body)) is False


@pytest.mark.parametrize("signature", [None, "", "not-a-signature", "é-non-ascii"])
def test_missing_or_malformed_signature_is_rejected_without_crashing(signature):
    assert verify_signature("secret", b'{"amount":1000}', signature) is False


# ---- the endpoint

@pytest.fixture
def client(monkeypatch):
    db = Database(":memory:")
    monkeypatch.setattr(api, "db", db)
    monkeypatch.setattr(api, "repository", TransactionRepository(db=db))
    monkeypatch.setattr(api, "payment_registry", PaymentRegistry(db=db))
    monkeypatch.setattr(api, "webhook_processor", WebhookProcessor(db=db))
    monkeypatch.setattr(api, "idempotency_store", IdempotencyStore(db=db))
    monkeypatch.setattr(api, "gateways", [FakeGateway(name="Fake", healthy=True, payment_results=[True])])
    monkeypatch.setattr(api, "webhook_secret", TEST_SECRET)
    return TestClient(api.app)


def create_processing_transaction(client):
    response = client.post("/transactions", json={"amount": 1000, "currency": "EUR"}, headers={"Idempotency-Key": "k"})
    return response.json()["transaction_id"]


def payload_for(transaction_id, amount=1000):
    return {"webhook_id": "wh_1", "transaction_id": transaction_id, "amount": amount, "status": "succeeded"}


def test_correctly_signed_webhook_is_processed(client):
    transaction_id = create_processing_transaction(client)

    response = post_signed_webhook(client, payload_for(transaction_id))

    assert response.status_code == 200
    assert response.json() == {"processed": True, "status": "ACCEPTED"}


def test_webhook_without_signature_is_rejected_and_changes_nothing(client):
    transaction_id = create_processing_transaction(client)

    response = client.post("/webhooks", json=payload_for(transaction_id))

    assert response.status_code == 401
    assert client.get(f"/transactions/{transaction_id}").json()["status"] == "PROCESSING"


def test_webhook_signed_with_the_wrong_secret_is_rejected(client):
    transaction_id = create_processing_transaction(client)

    response = post_signed_webhook(client, payload_for(transaction_id), secret="attacker-secret")

    assert response.status_code == 401
    assert client.get(f"/transactions/{transaction_id}").json()["status"] == "PROCESSING"


def test_body_changed_after_signing_is_rejected(client):
    transaction_id = create_processing_transaction(client)
    signed_body = json.dumps(payload_for(transaction_id, amount=1000)).encode()
    signature = sign_payload(TEST_SECRET, signed_body)
    tampered_body = json.dumps(payload_for(transaction_id, amount=1)).encode()

    response = client.post("/webhooks", content=tampered_body,
                           headers={"X-Signature": signature, "Content-Type": "application/json"})

    assert response.status_code == 401


def test_unsigned_webhook_gets_401_even_for_an_unknown_transaction(client):
    # Must not reveal (via 404 vs 401) which transaction ids exist
    response = client.post("/webhooks", json=payload_for("does-not-exist"))
    assert response.status_code == 401


def test_signed_but_invalid_payload_returns_422(client):
    body = b'{"webhook_id":"wh_1"}'
    response = client.post("/webhooks", content=body,
                           headers={"X-Signature": sign_payload(TEST_SECRET, body), "Content-Type": "application/json"})
    assert response.status_code == 422


def test_webhooks_are_refused_when_no_secret_is_configured(client, monkeypatch):
    transaction_id = create_processing_transaction(client)
    monkeypatch.setattr(api, "webhook_secret", None)

    response = post_signed_webhook(client, payload_for(transaction_id))

    assert response.status_code == 500
    assert client.get(f"/transactions/{transaction_id}").json()["status"] == "PROCESSING"
