from gateways.razorpaymock import RazorpayMock
from gateways.stripemock import StripeMock
from gateways.payumock import PayUMock
from gateways.upimock import UPIMock
from core.transaction import Transaction
from core.status import Status
from core.webhook import WebhookProcessor
from core.orchestrator import process_with_failover
from tests.fake_gateway import FakeGateway
from core.logging_config import setup_logging
from core.repository import TransactionRepository
from core.payment_registry import PaymentRegistry
import logging

setup_logging()

logger=logging.getLogger(__name__)

def demo_circuit_breaker():
    logger.info("--- Demonstratie Circuit Breaker ---")
    bad_gateway=FakeGateway(name="BadGateway",healthy=True,payment_results=[False,False,False])
    t=Transaction(100,"EUR")
    process_with_failover([bad_gateway],t,[Status.PROCESSING],delay=0)
    logger.info(f"Starea circuit breaker-ului dupa esecuri repetate: {bad_gateway.circuit_breaker.state}")

    t2=Transaction(100,"EUR")
    process_with_failover([bad_gateway],t2,[Status.PROCESSING],delay=0)
    logger.info(f"A doua tranzactie pe acelasi gateway - a fost sarita direct? Rezultat: {t2.status}")

def main():
    gateways=[RazorpayMock(),StripeMock(),PayUMock(),UPIMock()]
    transactions={}
    webhook_processor=WebhookProcessor()
    repository=TransactionRepository()
    payment_registry=PaymentRegistry()
    t=Transaction(200,"LEU")
    transactions[t.transaction_id]=t
    process_with_failover(gateways,t,[Status.PROCESSING],repository=repository,payment_registry=payment_registry)

    logger.info(f"Status inainte de webhook: {t.status}")

    payload={
        "webhook_id": "wh_100",
        "transaction_id" : t.transaction_id,
        "amount" : t.amount,
        "status" : "succeeded"
    }

    webhook_processor.receive_webhook(payload,transactions)

    logger.info(f"Status dupa webhook: {t.status}")
    t1=Transaction(500)
    process_with_failover(gateways,t1,[Status.ACCEPTED,Status.PROCESSING])
    demo_circuit_breaker()
if __name__ == "__main__":
    main()