from core.transaction import Transaction
from core.status import Status
import logging
import sqlite3

logger=logging.getLogger(__name__)

class WebhookProcessor:
    def __init__(self,db_path="transactions.db"):
        self.connection=sqlite3.connect(db_path,check_same_thread=False)
        self._create_table()


    def _create_table(self):
        self.connection.execute("""
        CREATE TABLE IF NOT EXISTS processed_webhooks (
            webhook_id TEXT PRIMARY KEY
            )
        """)
        self.connection.commit()

    def _is_webhook_processed(self,webhook_id:str) ->bool:
        cursor=self.connection.execute(
             "SELECT 1 FROM processed_webhooks WHERE webhook_id=?",
             (webhook_id,)
         )
        return cursor.fetchone() is not None

    def _mark_webhook_processed(self,webhook_id:str) :
        self.connection.execute(
            "INSERT OR REPLACE INTO processed_webhooks (webhook_id) VALUES (?)",
            (webhook_id,)
        )
        self.connection.commit()

    def receive_webhook(self,payload:dict,transactions:dict[str,Transaction]) -> bool:
        webhook_id=payload["webhook_id"]
        if self._is_webhook_processed(webhook_id):
            logger.info(f"Webhook {webhook_id} deja procesat, ignorat")
            return False

        self._mark_webhook_processed(webhook_id)

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
