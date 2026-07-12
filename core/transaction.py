from datetime import datetime
import time
from core.status import Status, VALID_TRANSITIONS

class Transaction:
    last_id=0

    def __init__(self,amount=0,currency="EUR",status:Status=Status.PENDING):
        Transaction.last_id+=1
        self.transaction_id=Transaction.last_id
        self.amount=amount
        self.currency=currency
        self.status=status
        self.created_at=datetime.now()
        self.updated_at=datetime.now()


    def change_status(self,new_status:Status):
        if new_status not in VALID_TRANSITIONS[self.status]:
            raise ValueError(f"Nu poti trece din {self.status} in {new_status}")
        self.status=new_status
        time.sleep(1)
        self.updated_at=datetime.now()

    def try_change_status(self,new_status:Status) -> bool:
        try:
            self.change_status(new_status)
            return True
        except ValueError as e:
            print(f"Eroare la tranzactia {self.transaction_id} : {e}")
            return False

    def __str__(self):
        return (f"Tranzactia cu ID-ul : {self.transaction_id} este pe status-ul : {self.status.value}, cu data crearii"
                f" : {self.created_at.strftime('%d-%m-%Y %H:%M:%S')}, si data actualizarii : "
                f" {self.updated_at.strftime('%d-%m-%Y %H:%M:%S')}")
