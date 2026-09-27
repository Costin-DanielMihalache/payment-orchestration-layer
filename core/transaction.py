from datetime import datetime
import time
import uuid
from core.status import Status, VALID_TRANSITIONS
import logging

logger=logging.getLogger(__name__)

class Transaction:

    def __init__(self,amount=0,currency="EUR",status:Status=Status.PENDING):
        self.transaction_id=str(uuid.uuid4())
        self.amount=amount
        self.currency=currency
        self.status=status
        self.created_at=datetime.now()
        self.updated_at=datetime.now()


    def change_status(self,new_status:Status,delay=0.1):
        if new_status not in VALID_TRANSITIONS[self.status]:
            raise ValueError(f"Cannot transition from {self.status} to {new_status}")
        self.status=new_status
        time.sleep(delay) # simulates real processing latency (I/O to the gateway)
        self.updated_at=datetime.now()

    def try_change_status(self,new_status:Status,delay=0.1) -> bool:
        # Wrapper that doesn't propagate the exception - orchestrator.py
        # handles a transition failure differently depending on whether the
        # payment already succeeded or the transition fails before the
        # payment is attempted, so the caller needs to check the result
        # without a try/except at every step
        try:
            self.change_status(new_status,delay=delay)
            return True
        except ValueError as e:
            logger.error(f"Error on transaction {self.transaction_id} : {e}")
            return False

    def __str__(self):
        return (f"Transaction with ID: {self.transaction_id} is in status: {self.status.value}, created on"
                f" : {self.created_at.strftime('%d-%m-%Y %H:%M:%S')}, and updated on: "
                f" {self.updated_at.strftime('%d-%m-%Y %H:%M:%S')}")

    @classmethod
    def from_row(cls,transaction_id,amount,currency,status,created_at,updated_at):
        transaction=cls.__new__(cls)
        transaction.transaction_id=transaction_id
        transaction.amount=amount
        transaction.currency=currency
        transaction.status=status
        transaction.created_at=created_at
        transaction.updated_at=updated_at
        return transaction
