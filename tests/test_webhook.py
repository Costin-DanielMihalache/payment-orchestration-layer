from core.webhook import WebhookProcessor
from core.transaction import Transaction
from core.status import Status

def test_webhook_succeeded_updates_transaction_to_accepted():
    t=Transaction(500,"LEU")
    t.change_status(Status.PROCESSING,delay=0)
    transactions={t.transaction_id:t}

    processor=WebhookProcessor(db_path=":memory:")

    payload={
        "webhook_id":"wh_001",
        "transaction_id":t.transaction_id,
        "amount":500,
        "status":"succeeded"
    }

    result=processor.receive_webhook(payload,transactions)
    assert result is True
    assert t.status==Status.ACCEPTED

def test_duplicate_webhook_is_ignored():
    t=Transaction(500,"LEU")
    t.change_status(Status.PROCESSING,delay=0)
    transactions={t.transaction_id:t}

    processor=WebhookProcessor(db_path=":memory:")
    payload={
        "webhook_id":"wh_002",
        "transaction_id":t.transaction_id,
        "amount":500,
        "status":"succeeded"
    }

    first_result=processor.receive_webhook(payload,transactions)
    second_result=processor.receive_webhook(payload,transactions)

    assert first_result is True
    assert second_result is False
    assert t.status == Status.ACCEPTED

def test_transaction_not_found_rejected():
    transactions={}

    processor=WebhookProcessor(db_path=":memory:")

    payload={
        "webhook_id":"wh_003",
        "transaction_id":"id-inexistent",
        "amount":500,
        "status":"succeeded"
    }

    result=processor.receive_webhook(payload,transactions)

    assert result is False


def test_amount_mismatch_rejected():
    t=Transaction(500,"LEU")
    t.change_status(Status.PROCESSING,delay=0)
    transactions={t.transaction_id:t}

    processor=WebhookProcessor(db_path=":memory:")

    payload={
        "webhook_id":"wh_004",
        "transaction_id":t.transaction_id,
        "amount":999,
        "status":"succeeded"
    }

    result=processor.receive_webhook(payload,transactions)

    assert result is False
    assert t.status==Status.PROCESSING

def test_webhook_on_pending_transaction_returns_false():
    t=Transaction(500,"RON")
    transactions={t.transaction_id:t}
    processor=WebhookProcessor(db_path=":memory:")
    payload={"webhook_id":"wh_005","transaction_id":t.transaction_id,"amount":500,"status":"succeeded"}

    result=processor.receive_webhook(payload,transactions)

    assert result is False
    assert t.status==Status.PENDING


def test_unknown_webhook_status_is_ignored():
    t=Transaction(500,"RON")
    t.change_status(Status.PROCESSING,delay=0)
    transactions={t.transaction_id:t}
    processor=WebhookProcessor(db_path=":memory:")
    payload={"webhook_id":"wh_006","transaction_id":t.transaction_id,"amount":500,"status":"refunded"}

    result=processor.receive_webhook(payload,transactions)

    assert result is False
    assert t.status==Status.PROCESSING


def test_webhook_not_marked_processed_when_amount_mismatch():
    t=Transaction(500,"RON")
    t.change_status(Status.PROCESSING,delay=0)
    transactions={t.transaction_id:t}
    processor=WebhookProcessor(db_path=":memory:")
    bad={"webhook_id":"wh_007","transaction_id":t.transaction_id,"amount":999,"status":"succeeded"}
    good={"webhook_id":"wh_007","transaction_id":t.transaction_id,"amount":500,"status":"succeeded"}

    assert processor.receive_webhook(bad,transactions) is False
    assert processor.receive_webhook(good,transactions) is True
    assert t.status==Status.ACCEPTED