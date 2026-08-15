from core.orchestrator import process_with_failover
from core.transaction import Transaction
from tests.fake_gateway import FakeGateway
from core.status import Status
from core.breaker import CircuitState
from core.payment_registry import PaymentRegistry


def test_failover_opening_circuit_breaker():
    gateway=FakeGateway(name="FakeGateway",healthy=True,payment_results=[False,False,False])
    payment_registry=PaymentRegistry(db_path=":memory:")

    transaction=Transaction(100,"EUR")
    process_with_failover([gateway],transaction,[Status.PROCESSING,Status.ACCEPTED],delay=0,payment_registry=payment_registry)

    assert gateway.circuit_breaker.state==CircuitState.OPEN