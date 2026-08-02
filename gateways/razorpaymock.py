from gateways.paymentgateway import PaymentGateway
from core.transaction import Transaction
import random
import logging

logger=logging.getLogger(__name__)

class RazorpayMock(PaymentGateway):
    def __init__(self):
        super().__init__("RazorpayMock")
        self.is_healthy=random.random()>0.5

    def process_payment(self,transaction:Transaction) -> bool:
        if not self.is_healthy:
            return False
        success=random.random()>0.5
        logger.info(f"Razorpay proceseaza tranzactia cu ID-ul {transaction.transaction_id}: {'succes' if success else 'esec'}")
        return success

    def check_health(self) -> bool:
        return self.is_healthy