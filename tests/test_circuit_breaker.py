from core.breaker import CircuitBreaker,CircuitState

def test_circuit_opens_after_threshold_failures():
    cb=CircuitBreaker(failure_threshold=3,recovery_timeout=10)

    cb.record_failure()
    cb.record_failure()

    assert cb.state==CircuitState.CLOSED

    cb.record_failure()

    assert cb.state==CircuitState.OPEN


def test_circuit_moves_to_half_open_after_timeout():
    cb=CircuitBreaker(failure_threshold=1,recovery_timeout=0)
    cb.record_failure()
    assert cb.state==CircuitState.OPEN

    cb.try_change_state_to_half_open()

    assert cb.state==CircuitState.HALF_OPEN

def test_allow_request_false_when_open():
    cb=CircuitBreaker(failure_threshold=1,recovery_timeout=10)
    cb.record_failure()

    assert cb.allow_request() is False

def test_record_success_resets_to_closed():
    cb=CircuitBreaker(failure_threshold=1,recovery_timeout=10)
    cb.record_failure()

    assert cb.state==CircuitState.OPEN

    cb.record_success()

    assert cb.state==CircuitState.CLOSED
    assert cb.failure_count==0