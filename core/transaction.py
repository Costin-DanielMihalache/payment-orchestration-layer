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
            raise ValueError(f"Nu poti trece din {self.status} in {new_status}")
        self.status=new_status
        time.sleep(delay)
        self.updated_at=datetime.now()

    def try_change_status(self,new_status:Status,delay=0.1) -> bool:
        try:
            self.change_status(new_status,delay=delay)
            return True
        except ValueError as e:
            logger.error(f"Eroare la tranzactia {self.transaction_id} : {e}")
            return False

    def __str__(self):
        return (f"Tranzactia cu ID-ul : {self.transaction_id} este pe status-ul : {self.status.value}, cu data crearii"
                f" : {self.created_at.strftime('%d-%m-%Y %H:%M:%S')}, si data actualizarii : "
                f" {self.updated_at.strftime('%d-%m-%Y %H:%M:%S')}")
