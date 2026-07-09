from gateways.paymentgateway import PaymentGateway
from core.transaction import Transaction
import random

class StripeMock(PaymentGateway):

    def __init__(self):
        self.is_healthy=random.random()>0.7

    def process_payment(self,transaction:Transaction ):
        if not self.is_healthy:
            return False
        success=random.random()>0.4
        print(f"StripeMock proceseaza tranzactia cu ID-ul {transaction.transaction_id} : {'success' if success else 'esec'}")
        return success

    def check_health(self) -> bool:
        return self.is_healthy