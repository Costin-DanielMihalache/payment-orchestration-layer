from core.transaction import Transaction
import logging
import sqlite3
from core.status import Status, WebhookStatus

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

        # Unknown statuses (e.g. "refunded", "pending") are ignored instead of
        # being treated as a failure
        try:
            webhook_status=WebhookStatus(payload["status"])
        except ValueError:
            logger.error(f"Webhook {webhook_id} has unknown status: {payload['status']}")
            return False

        transaction=transactions.get(payload["transaction_id"])
        if transaction is None:
            logger.error(f"Transaction {payload['transaction_id']} does not exist locally!")
            return False

        # Reconciliation: the amount in the webhook must match our local
        # amount exactly, otherwise we treat it as a possible fraud/gateway
        # error and don't update the status
        if payload["amount"] != transaction.amount:
            logger.error("Amounts do not match!")
            return False

        if transaction.status in (Status.ACCEPTED,Status.REJECTED):
            # Terminal state: a webhook confirming the same state is redundant
            # (normal, gateways resend), but one saying something else is a
            # serious contradiction and must be flagged, not applied silently
            if webhook_status==WebhookStatus.SUCCEEDED and transaction.status==Status.ACCEPTED:
                logger.warning(f"Redundant webhook, transaction {transaction.transaction_id} was already ACCEPTED")
                self._mark_webhook_processed(webhook_id)
                return True
            if webhook_status==WebhookStatus.FAILED and transaction.status==Status.REJECTED:
                logger.warning(f"Redundant webhook, transaction {transaction.transaction_id} was already REJECTED")
                self._mark_webhook_processed(webhook_id)
                return True
            logger.error(f"ALERT: webhook contradicts existing state! Transaction {transaction.transaction_id} was {transaction.status}, webhook says {webhook_status.value}")
            return False

        new_status=Status.ACCEPTED if webhook_status==WebhookStatus.SUCCEEDED else Status.REJECTED
        if not transaction.try_change_status(new_status):
            # Don't mark as processed: the webhook was not applied, so a
            # later resend must still be accepted
            return False

        # Mark as processed only after the webhook was actually applied
        self._mark_webhook_processed(webhook_id)
        return True