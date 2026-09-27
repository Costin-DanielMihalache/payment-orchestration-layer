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
        # Deduplication: real gateways resend the same webhook on timeout/no
        # response, so the same webhook_id can arrive more than once - we
        # only process it once
        if self._is_webhook_processed(webhook_id):
            logger.info(f"Webhook {webhook_id} already processed, ignored")
            return False

        self._mark_webhook_processed(webhook_id)

        transaction=transactions.get(payload["transaction_id"])
        if transaction is None:
            logger.error(f"Transaction {payload['transaction_id']} does not exist locally!")
            return False

        # Reconciliation: the amount in the webhook must match our local
        # amount exactly, otherwise we treat it as a possible fraud/gateway
        # error and don't update the status
        if payload["amount"] !=transaction.amount:
            logger.error(f"Amounts do not match!")
            return False

        if transaction.status in (Status.ACCEPTED,Status.REJECTED):
            # The transaction is already in a terminal state - a webhook
            # confirming the same state is redundant (normal, gateways resend),
            # but one saying something else is a serious contradiction
            # (possibly a spoofed webhook or a gateway bug) and must be
            # flagged, not applied silently
            if payload["status"]=="succeeded" and transaction.status==Status.ACCEPTED:
                logger.warning(f"Redundant webhook, transaction {transaction.transaction_id} was already ACCEPTED")
                return True
            if payload["status"] == "failed" and transaction.status==Status.REJECTED:
                logger.warning(f"Redundant webhook, transaction {transaction.transaction_id} was already REJECTED")
                return True
            logger.error(f"ALERT: webhook contradicts existing state! Transaction {transaction.transaction_id} was {transaction.status}, webhook says {payload['status']}")
            return False

        if payload["status"]== "succeeded":
            transaction.try_change_status(Status.ACCEPTED)
        else:
            transaction.try_change_status(Status.REJECTED)
        return True
