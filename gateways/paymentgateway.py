from abc import ABC, abstractmethod
from core.transaction import Transaction

class PaymentGateway(ABC):

    def __init__(self,name:str):
        self.name=name

    @abstractmethod
    def process_payment(self,transaction:Transaction) -> bool:
        pass

    @abstractmethod
    def check_health(self) -> bool:
        pass


