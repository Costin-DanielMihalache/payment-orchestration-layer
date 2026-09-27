from gateways.paymentgateway import PaymentGateway
from core.transaction import Transaction
import random
import logging

logger=logging.getLogger(__name__)


class StripeMock(PaymentGateway):

    def __init__(self):
        super().__init__("StripeMock")
        self.is_healthy=True

    def process_payment(self,transaction:Transaction ):
        if not self.is_healthy:
            return False
        success=random.random()>0.4
        logger.info(f"StripeMock is processing transaction ID {transaction.transaction_id} : {'success' if success else 'failure'}")
        return success

    def check_health(self) -> bool:
        self.is_healthy=random.random()>0.7
        return self.is_healthy