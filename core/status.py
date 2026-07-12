from enum import Enum

class Status(Enum):
    PENDING="PENDING"
    PROCESSING="PROCESSING"
    ACCEPTED="ACCEPTED"
    REJECTED="REJECTED"

VALID_TRANSITIONS={
    Status.PENDING: [Status.PROCESSING,Status.REJECTED],
    Status.PROCESSING : [Status.ACCEPTED, Status.REJECTED, Status.PENDING],
    Status.ACCEPTED : [],
    Status.REJECTED : []
}