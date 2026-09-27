from enum import Enum
import time
import logging

logger=logging.getLogger(__name__)

class CircuitState(Enum):
    CLOSED="closed"
    OPEN="open"
    HALF_OPEN="half_open"

class CircuitBreaker:
    def __init__(self,failure_threshold=3,recovery_timeout=10):
        self.state: CircuitState=CircuitState.CLOSED
        self.failure_threshold=failure_threshold
        self.recovery_timeout=recovery_timeout
        self.failure_count=0
        self.opened_at=None

    def record_failure(self):
        self.failure_count+=1
        if self.failure_count>=self.failure_threshold:
            self.state=CircuitState.OPEN
            self.opened_at=time.time()
            logger.warning(f"Circuit breaker opened after {self.failure_count} consecutive failures")

    def record_success(self):
        # Any success fully resets the counter instead of just decrementing it -
        # a gateway that works now is considered healthy regardless of past
        # failures (avoids staying "almost open" indefinitely)
        if self.state!=CircuitState.CLOSED:
            logger.info(f"Circuit breaker returns to CLOSED after a success (previous state: {self.state.value})")
        self.state=CircuitState.CLOSED
        self.failure_count=0

    def try_change_state_to_half_open(self):
        # HALF_OPEN = a single "test" transaction is let through after
        # recovery_timeout, to check whether the gateway has recovered,
        # without sending it all the traffic at once
        if self.state==CircuitState.OPEN and time.time()-self.opened_at>=self.recovery_timeout:
            self.state=CircuitState.HALF_OPEN
            logger.info("Circuit breaker transitions to HALP_OPEN, testing the gateway again")

    def allow_request(self) -> bool:
        self.try_change_state_to_half_open()
        if self.state==CircuitState.OPEN:
            return False
        return True
