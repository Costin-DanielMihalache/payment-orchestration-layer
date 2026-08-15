import time
from core.orchestrator import process_with_failover
from core.transaction import Transaction
from core.status import Status
from core.payment_registry import PaymentRegistry
from tests.fake_gateway import FakeGateway

def test_failover_completes_under_two_seconds():
    gateway1=FakeGateway(name="Gateway1",healthy=False)
    gateway2=FakeGateway(name="Gateway2",healthy=True,payment_results=[False,False,True])
    gateway3=FakeGateway(name="Gateway3",healthy=True,payment_results=[True])

    payment_registry=PaymentRegistry(db_path=":memory:")

    t=Transaction(100,"EUR")
    start=time.time()
    result=process_with_failover([gateway1,gateway2,gateway3],t,[Status.PROCESSING,Status.ACCEPTED],payment_registry=payment_registry)
    duration=time.time()-start

    assert result is True
    assert duration < 2.0