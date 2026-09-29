import pytest
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


def make_table(db):
    with db.transaction() as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS t (x INTEGER)")


def count_rows(db):
    return db.fetchone("SELECT COUNT(*) FROM t")[0]


def test_transaction_block_commits_on_success():
    db=Database(":memory:")
    make_table(db)

    with db.transaction() as connection:
        connection.execute("INSERT INTO t VALUES (1)")
        connection.execute("INSERT INTO t VALUES (2)")

    assert count_rows(db)==2


def test_transaction_block_rolls_back_on_exception():
    db=Database(":memory:")
    make_table(db)

    with pytest.raises(RuntimeError):
        with db.transaction() as connection:
            connection.execute("INSERT INTO t VALUES (1)")
            raise RuntimeError("crash in the middle")

    assert count_rows(db)==0


def test_nested_blocks_join_the_outer_transaction():
    db=Database(":memory:")
    make_table(db)

    with pytest.raises(RuntimeError):
        with db.transaction():
            with db.transaction() as connection:
                connection.execute("INSERT INTO t VALUES (1)")
            # the inner block finished fine, but it must not have committed on its own
            raise RuntimeError("outer block fails")

    assert count_rows(db)==0


def test_webhook_not_marked_as_processed_if_saving_the_status_fails(monkeypatch):
    db=Database(":memory:")
    repository=TransactionRepository(db=db)
    processor=WebhookProcessor(db=db)
    t=Transaction(500,"EUR")
    t.change_status(Status.PROCESSING,delay=0)
    repository.save(t)

    def failing_save(transaction):
        raise ConcurrentModificationError("someone else changed it")
    monkeypatch.setattr(repository,"save",failing_save)

    payload={"webhook_id":"wh_1","transaction_id":t.transaction_id,"amount":500,"status":"succeeded"}
    with pytest.raises(ConcurrentModificationError):
        processor.receive_webhook(payload,{t.transaction_id:t},repository=repository)

    # nothing was committed: the gateway's retry must still be accepted
    assert processor._is_webhook_processed("wh_1") is False
    assert repository.get(t.transaction_id).status==Status.PROCESSING


def test_webhook_marks_and_saves_status_together():
    db=Database(":memory:")
    repository=TransactionRepository(db=db)
    processor=WebhookProcessor(db=db)
    t=Transaction(500,"EUR")
    t.change_status(Status.PROCESSING,delay=0)
    repository.save(t)

    payload={"webhook_id":"wh_1","transaction_id":t.transaction_id,"amount":500,"status":"succeeded"}
    assert processor.receive_webhook(payload,{t.transaction_id:t},repository=repository) is True

    assert processor._is_webhook_processed("wh_1") is True
    assert repository.get(t.transaction_id).status==Status.ACCEPTED


def test_webhook_rejects_repository_with_a_different_database():
    processor=WebhookProcessor(db=Database(":memory:"))
    other_repository=TransactionRepository(db=Database(":memory:"))
    t=Transaction(500,"EUR")
    t.change_status(Status.PROCESSING,delay=0)

    payload={"webhook_id":"wh_1","transaction_id":t.transaction_id,"amount":500,"status":"succeeded"}
    with pytest.raises(ValueError):
        processor.receive_webhook(payload,{t.transaction_id:t},repository=other_repository)


def test_failed_save_does_not_leave_the_idempotency_key_reserved(monkeypatch):
    db=Database(":memory:")
    monkeypatch.setattr(api,"db",db)
    repository = TransactionRepository(db=db)
    monkeypatch.setattr(api, "repository", repository)
    monkeypatch.setattr(api,"payment_registry",PaymentRegistry(db=db))
    monkeypatch.setattr(api,"webhook_processor",WebhookProcessor(db=db))
    monkeypatch.setattr(api,"idempotency_store",IdempotencyStore(db=db))
    monkeypatch.setattr(api,"gateways",[FakeGateway(name="Fake",healthy=True,payment_results=[True])])
    client=TestClient(api.app)

    real_save=repository.save
    calls={"n":0}
    def flaky_save(transaction):
        calls["n"]+=1
        if calls["n"]==1:
            raise RuntimeError("disk error")
        real_save(transaction)
    monkeypatch.setattr(repository,"save",flaky_save)

    headers={"Idempotency-Key":"key-1"}
    with pytest.raises(RuntimeError):
        client.post("/transactions",json={"amount":1000,"currency":"EUR"},headers=headers)

    # If the key had stayed reserved, this retry would get 409
    retry=client.post("/transactions",json={"amount":1000,"currency":"EUR"},headers=headers)
    assert retry.status_code==200
    assert retry.json()["status"]=="PROCESSING"