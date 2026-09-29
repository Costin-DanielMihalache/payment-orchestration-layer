import sqlite3
from core.database import Database

# Separate from TransactionRepository: here we track, per
# (transaction, gateway) pair, whether the payment was already processed
# successfully - used strictly for idempotency in orchestrator.py, not for
# the transaction's overall state (that's repository.py's job)
class PaymentRegistry:
    def __init__(self,db_path="transactions.db",db:Database|None=None):
        self.db=db if db is not None else Database(db_path)
        self._create_table()

    def _create_table(self):
        with self.db.transaction() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS processed_payments (
                    transaction_id TEXT,
                    gateway_name TEXT,
                    PRIMARY KEY (transaction_id,gateway_name)
                )
            """)

    def is_processed(self,transaction_id:str,gateway_name:str) -> bool:
        row=self.db.fetchone(
            "SELECT 1 FROM processed_payments WHERE transaction_id=? AND gateway_name=?",
            (transaction_id,gateway_name)
        )
        return row is not None

    def mark_processed(self,transaction_id:str,gateway_name:str):
        with self.db.transaction() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO processed_payments (transaction_id,gateway_name) VALUES (?,?)",
                (transaction_id,gateway_name)
            )