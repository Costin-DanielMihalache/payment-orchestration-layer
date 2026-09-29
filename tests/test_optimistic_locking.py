import pytest
from datetime import datetime
from fastapi.testclient import TestClient
import api
from core.database import Database
from core.repository import TransactionRepository, ConcurrentModificationError
from core.payment_registry import PaymentRegistry
from core.webhook import WebhookProcessor
from core.idempotency import IdempotencyStore
from core.transaction import Transaction
from core.status import Status
from tests.fake_gateway import FakeGateway


def test_version_is_0_before_the_first_save_and_1_after():
    repository=TransactionRepository(db_path=":memory:")
    t=Transaction(200,"EUR")
    assert t.version==0

    repository.save(t)

    assert t.version==1
    assert repository.get(t.transaction_id).version==1


def test_every_save_increments_the_version():
    repository=TransactionRepository(db_path=":memory:")
    t=Transaction(200,"EUR")
    repository.save(t)
    t.change_status(Status.PROCESSING,delay=0)
    repository.save(t)
    t.change_status(Status.ACCEPTED,delay=0)
    repository.save(t)

    assert t.version==3
    assert repository.get(t.transaction_id).version==3


def test_stale_save_raises_and_does_not_overwrite_the_newer_state():
    repository=TransactionRepository(db_path=":memory:")
    t=Transaction(200,"EUR")
    t.change_status(Status.PROCESSING,delay=0)
    repository.save(t)

    first=repository.get(t.transaction_id)
    second=repository.get(t.transaction_id)
    first.change_status(Status.ACCEPTED,delay=0)
    repository.save(first)

    second.change_status(Status.REJECTED,delay=0)
    with pytest.raises(ConcurrentModificationError):
        repository.save(second)

    assert repository.get(t.transaction_id).status==Status.ACCEPTED


def test_saving_a_new_transaction_with_an_existing_id_raises():
    repository=TransactionRepository(db_path=":memory:")
    t=Transaction(200,"EUR")
    repository.save(t)

    duplicate=Transaction(200,"EUR")
    duplicate.transaction_id=t.transaction_id  # version is still 0: it thinks it is new

    with pytest.raises(ConcurrentModificationError):
        repository.save(duplicate)


def test_old_database_without_version_column_is_migrated():
    db=Database(":memory:")
    with db.transaction() as connection:
        connection.execute("""
            CREATE TABLE transactions (
                transaction_id TEXT PRIMARY KEY,
                amount REAL,
                currency TEXT,
                status TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        now=datetime.now().isoformat()
        connection.execute(
            "INSERT INTO transactions VALUES (?,?,?,?,?,?)",
            ("old-1",500,"EUR","PROCESSING",now,now)
        )

    repository=TransactionRepository(db=db)

    old=repository.get("old-1")
    assert old.version==1
    old.change_status(Status.ACCEPTED,delay=0)
    repository.save(old)
    assert repository.get("old-1").version==2


def test_api_returns_409_on_conflict_and_the_webhook_retry_is_then_accepted(monkeypatch):
    db=Database(":memory:")
    monkeypatch.setattr(api,"db",db)
    repository = TransactionRepository(db=db)
    monkeypatch.setattr(api, "repository", repository)
    monkeypatch.setattr(api,"payment_registry",PaymentRegistry(db=db))
    monkeypatch.setattr(api,"webhook_processor",WebhookProcessor(db=db))
    monkeypatch.setattr(api,"idempotency_store",IdempotencyStore(db=db))
    monkeypatch.setattr(api,"gateways",[FakeGateway(name="Fake",healthy=True,payment_results=[True])])
    client=TestClient(api.app)

    created=client.post("/transactions",json={"amount":1000,"currency":"EUR"},headers={"Idempotency-Key":"k"})
    transaction_id=created.json()["transaction_id"]
    payload={"webhook_id":"wh_1","transaction_id":transaction_id,"amount":1000,"status":"succeeded"}

    # Simulate another request saving the same transaction right after the
    # webhook endpoint loaded it
    real_get=repository.get
    def get_then_conflict(tid):
        loaded=real_get(tid)
        concurrent=real_get(tid)
        concurrent.updated_at=datetime.now()
        api.repository.save(concurrent)
        return loaded
    monkeypatch.setattr(repository,"get",get_then_conflict)

    conflict=client.post("/webhooks",json=payload)
    assert conflict.status_code==409

    monkeypatch.setattr(repository,"get",real_get)
    assert client.get(f"/transactions/{transaction_id}").json()["status"]=="PROCESSING"

    # The conflicting attempt must not have marked the webhook as processed
    retry=client.post("/webhooks",json=payload)
    assert retry.json()=={"processed":True,"status":"ACCEPTED"}