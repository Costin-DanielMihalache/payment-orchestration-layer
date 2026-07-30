from enum import Enum
import time

class CircuitState(Enum):
    CLOSED="closed"
    OPEN="open"
    HALF_OPEN="half_open"

class CircuitBreaker:
    def __init__(self,failure_threshold=3,recovery_timeout=10):
        self.state=CircuitState.CLOSED
        self.failure_threshold=failure_threshold
        self.recovery_timeout=recovery_timeout
        self.failure_count=0
        self.opened_at=None

    def record_failure(self):
        self.failure_count+=1
        if self.failure_count>=self.failure_threshold:
            self.state=CircuitState.OPEN
            self.opened_at=time.time()

    def record_success(self):
        self.state=CircuitState.CLOSED
        self.failure_count=0

    def try_change_state_to_half_open(self):
        if self.state==CircuitState.OPEN and time.time()-self.opened_at>=self.recovery_timeout:
            self.state=CircuitState.HALF_OPEN

    def allow_request(self) -> bool:
        self.try_change_state_to_half_open()
        if self.state==CircuitState.OPEN:
            return False
        return True
