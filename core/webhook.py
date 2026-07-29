from core.transaction import Transaction
from core.status import Status

class WebhookProcessor:
    def __init__(self):
        self.processed_webhook_ids=set()

    def receive_webhook(self,payload:dict,transactions:dict[str,Transaction]) -> bool:
        webhook_id=payload["webhook_id"]
        if webhook_id in self.processed_webhook_ids:
            print(f"Webhook {webhook_id} deja procesat, ignorat")
            return False

        self.processed_webhook_ids.add(webhook_id)

        transaction=transactions.get(payload["transaction_id"])
        if transaction is None:
            print(f"Tranzactia {payload['transaction_id']} nu exista local!")
            return False

        if payload["amount"] !=transaction.amount:
            print(f"Sumele nu se potrivesc!")
            return False

        if transaction.status in (Status.ACCEPTED,Status.REJECTED):
            if payload["status"]=="succeeded" and transaction.status==Status.ACCEPTED:
                print(f"Webhook redundant, tranzactia {transaction.transaction_id} era deja ACCEPTED")
                return True
            if payload["status"] == "failed" and transaction.status==Status.REJECTED:
                print(f"Webhook redundant, tranzactia {transaction.transaction_id} era deja REJECTED")
                return True
            print(f"ALERTA: webhook contrazice starea existenta! Tranzactia {transaction.transaction_id} era {transaction.status} webhook spune {payload['status']}")
            return False

        if payload["status"]== "succeeded":
            transaction.try_change_status(Status.ACCEPTED)
        else:
            transaction.try_change_status(Status.REJECTED)
        return True
