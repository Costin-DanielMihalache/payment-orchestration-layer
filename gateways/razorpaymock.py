from gateways.paymentgateway import PaymentGateway
from core.transaction import Transaction
import random

class RazorpayMock(PaymentGateway):
    def __init__(self):
        self.is_healthy=random.random()>0.5

    def process_payment(self,transaction:Transaction) -> bool:
        if not self.is_healthy:
            return False
        success=random.random()>0.5
        print(f"Razorpay proceseaza tranzactia cu ID-ul {transaction.transaction_id}: {'succes' if success else 'esec'}")
        return success

    def check_health(self) -> bool:
        return self.is_healthy