from abc import ABC, abstractmethod
from core.transaction import Transaction
from core.breaker import CircuitBreaker

class PaymentGateway(ABC):

    def __init__(self,name:str):
        self.name=name
        self.total_attempts=0
        self.successful_attempts=0
        self.circuit_breaker=CircuitBreaker()

    @property
    def success_rate(self) -> float:
        # A gateway with no attempts yet starts with a success rate of 1.0
        # (optimistic), not 0.0 - otherwise a new  gateway would never be
        # tried first, since it would always be sorted last by
        # sort_gateways_by_success_rate
        if self.total_attempts == 0:
            return 1.0
        return self.successful_attempts/self.total_attempts

    @abstractmethod
    def process_payment(self,transaction:Transaction) -> bool:
        pass

    @abstractmethod
    def check_health(self) -> bool:
        pass


