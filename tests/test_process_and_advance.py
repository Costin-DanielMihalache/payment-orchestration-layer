from main import process_and_advance
from core.transaction import Transaction
from core.status import Status
from tests.fake_gateway import FakeGateway
import pytest

def test_all_attempts_fail_returns_false():
    gateway=FakeGateway(healthy=True,payment_results=[False,False,False])
    t=Transaction(100,"EUR")
    result=process_and_advance(gateway,t,Status.PROCESSING,delay=0)
    assert result is False
    assert t.status==Status.PENDING

def test_process_and_advance_raises_on_successful_payment_invalid_transition():
    gateway1=FakeGateway(name="Gateway1",healthy=True,payment_results=[True])
    t=Transaction(100,"EUR")

    with pytest.raises(RuntimeError):
        process_and_advance(gateway1,t,Status.ACCEPTED,delay=0)