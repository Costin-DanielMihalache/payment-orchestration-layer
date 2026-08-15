from core.orchestrator import process_with_failover
from core.transaction import Transaction
from core.status import Status
from tests.fake_gateway import FakeGateway
from core.payment_registry import PaymentRegistry

def test_failover_reaches_third_gateway():
    gateway1=FakeGateway(name="Gateway1",healthy=False)
    gateway2=FakeGateway(name="Gateway2",healthy=True,payment_results=[False,False,False])
    gateway3=FakeGateway(name="Gateway3",healthy=True,payment_results=[True])
    payment_registry=PaymentRegistry(db_path=":memory:")

    t=Transaction(100,"EUR")
    result=process_with_failover([gateway1,gateway2,gateway3],t,[Status.PROCESSING,Status.ACCEPTED],delay=0,payment_registry=payment_registry)

    assert result is True
    assert t.status==Status.ACCEPTED


def test_failover_all_gateways_fail_rejects_transaction():
    gateway1=FakeGateway(name="Gateway1",healthy=False)
    gateway2=FakeGateway(name="Gateway2",healthy=True,payment_results=[False,False,False])
    gateway3=FakeGateway(name="Gateway3",healthy=False)
    payment_registry=PaymentRegistry(db_path=":memory:")

    t=Transaction(100,"EUR")
    result=process_with_failover([gateway1,gateway2,gateway3],t,[Status.PROCESSING,Status.ACCEPTED],delay=0,payment_registry=payment_registry)

    assert result is False
    assert t.status==Status.REJECTED

def test_failover_stops_when_status_transition_fails_after_successful_payment():
    gateway1=FakeGateway(name="Gateway1",healthy=True,payment_results=[True])

    t=Transaction(100,"EUR")
    result=process_with_failover([gateway1],t,[Status.ACCEPTED,Status.PROCESSING],delay=0)

    assert result is False
    assert t.status== Status.PENDING
    assert gateway1.call_count==1