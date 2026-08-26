import sqlite3

class PaymentRegistry:
    def __init__(self,db_path="transactions.db"):
        self.connection=sqlite3.connect(db_path,check_same_thread=False)
        self._create_table()

    def _create_table(self):
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS processed_payments (
                transaction_id TEXT,
                gateway_name TEXT,
                PRIMARY KEY (transaction_id,gateway_name)
            )
        """)
        self.connection.commit()

    def is_processed(self,transaction_id:str,gateway_name:str) -> bool:
        cursor=self.connection.execute(
            "SELECT 1 FROM processed_payments WHERE transaction_id=? AND gateway_name=?",
            (transaction_id,gateway_name)
        )
        return cursor.fetchone() is not None

    def mark_processed(self,transaction_id:str,gateway_name:str):
        self.connection.execute(
            "INSERT OR REPLACE INTO processed_payments (transaction_id,gateway_name) VALUES (?,?)",
            (transaction_id,gateway_name)
        )
        self.connection.commit()