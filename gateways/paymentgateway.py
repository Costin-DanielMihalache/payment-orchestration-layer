from abc import ABC, abstractmethod
from core.transaction import Transaction

class PaymentGateway(ABC):

    def __init__(self,name:str):
        self.name=name
        self.total_attempts=0
        self.successful_attempts=0

    @property
    def success_rate(self) -> float:
        if self.total_attempts == 0:
            return 1.0
        return self.successful_attempts/self.total_attempts

    @abstractmethod
    def process_payment(self,transaction:Transaction) -> bool:
        pass

    @abstractmethod
    def check_health(self) -> bool:
        pass


