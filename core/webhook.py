from core.transaction import Transaction
from core.status import Status
import logging

logger=logging.getLogger(__name__)

class WebhookProcessor:
    def __init__(self):
        self.processed_webhook_ids=set()

    def receive_webhook(self,payload:dict,transactions:dict[str,Transaction]) -> bool:
        webhook_id=payload["webhook_id"]
        if webhook_id in self.processed_webhook_ids:
            logger.info(f"Webhook {webhook_id} deja procesat, ignorat")
            return False

        self.processed_webhook_ids.add(webhook_id)

        transaction=transactions.get(payload["transaction_id"])
        if transaction is None:
            logger.error(f"Tranzactia {payload['transaction_id']} nu exista local!")
            return False

        if payload["amount"] !=transaction.amount:
            logger.error(f"Sumele nu se potrivesc!")
            return False

        if transaction.status in (Status.ACCEPTED,Status.REJECTED):
            if payload["status"]=="succeeded" and transaction.status==Status.ACCEPTED:
                logger.warning(f"Webhook redundant, tranzactia {transaction.transaction_id} era deja ACCEPTED")
                return True
            if payload["status"] == "failed" and transaction.status==Status.REJECTED:
                logger.warning(f"Webhook redundant, tranzactia {transaction.transaction_id} era deja REJECTED")
                return True
            logger.error(f"ALERTA: webhook contrazice starea existenta! Tranzactia {transaction.transaction_id} era {transaction.status}, webhook spune {payload['status']}")
            return False

        if payload["status"]== "succeeded":
            transaction.try_change_status(Status.ACCEPTED)
        else:
            transaction.try_change_status(Status.REJECTED)
        return True
