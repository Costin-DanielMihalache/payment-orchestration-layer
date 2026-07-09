from enum import Enum

class Status(Enum):
    PENDING="PENDING"
    PROCESSING="PROCESSING"
    ACCEPTED="ACCEPTED"
    REJECTED="REJECTED"

VALID_TRANSITIONS={
    Status.PENDING: [Status.PROCESSING],
    Status.PROCESSING : [Status.ACCEPTED, Status.REJECTED],
    Status.ACCEPTED : [],
    Status.REJECTED : []
}