from abc import ABC, abstractmethod
from core.transaction import Transaction

class PaymentGateway(ABC):

    @abstractmethod
    def process_payment(self,transaction:Transaction) -> bool:
        pass

    @abstractmethod
    def check_health(self) -> bool:
        pass


