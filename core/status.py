from enum import Enum

class WebhookStatus(Enum):
    SUCCEEDED="succeeded"
    FAILED="failed"

class Status(Enum):
    PENDING="PENDING"
    PROCESSING="PROCESSING"
    ACCEPTED="ACCEPTED"
    REJECTED="REJECTED"

# Transaction state machine: explicitly defines which transitions are allowed,
# so a transaction can never end up in an invalid state (e.g. jumping from
# ACCEPTED straight to PROCESSING). PROCESSING -> PENDING is allowed so it can
# be retried on another gateway during failover (see orchestrator.py).
# ACCEPTED/REJECTED are terminal states - no outgoing transitions.
VALID_TRANSITIONS={
    Status.PENDING: [Status.PROCESSING,Status.REJECTED],
    Status.PROCESSING : [Status.ACCEPTED, Status.REJECTED, Status.PENDING],
    Status.ACCEPTED : [],
    Status.REJECTED : []
}