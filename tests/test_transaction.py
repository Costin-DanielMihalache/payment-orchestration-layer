import pytest
from core.transaction import Transaction
from core.status import Status

def test_transaction_starts_as_pending():
    t=Transaction(100,"EUR")
    assert t.status == Status.PENDING

def test_invalid_transition_raises_error():
    t=Transaction(100,"EUR")
    with pytest.raises(ValueError):
        t.change_status(Status.ACCEPTED,0)

def test_valid_transition_works():
    t=Transaction(100,"EUR")
    t.change_status(Status.PROCESSING,0)
    assert t.status==Status.PROCESSING

def test_try_change_status_returns_false_on_invalid():
    t=Transaction(100,"EUR")
    result=t.try_change_status(Status.ACCEPTED,0)
    assert result is False
    assert t.status==Status.PENDING