import sqlite3
from core.transaction import Transaction
from core.status import Status
from datetime import datetime

class TransactionRepository:
    def __init__(self,db_path="transactions.db"):
        self.connection=sqlite3.connect(db_path)
        self._create_table()

    def _create_table(self):
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id TEXT PRIMARY KEY,
                amount REAL,
                currency TEXT,
                status TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        self.connection.commit()

    def save(self,transaction:Transaction):
        self.connection.execute(
            "INSERT OR REPLACE INTO transactions (transaction_id,amount,currency,status,created_at,updated_at) VALUES (?,?,?,?,?,?)",
            (transaction.transaction_id,transaction.amount,transaction.currency,transaction.status.value,transaction.created_at.isoformat(),transaction.updated_at.isoformat())
        )
        self.connection.commit()

    def get(self,transaction_id:str) ->Transaction | None:
        cursor=self.connection.execute(
            "SELECT * FROM transactions WHERE transaction_id=?",
            (transaction_id,)
        )
        row=cursor.fetchone()
        if row is None:
            return None
        return Transaction.from_row(
            transaction_id=row[0],
            amount=row[1],
            currency=row[2],
            status=Status(row[3]),
            created_at=datetime.fromisoformat(row[4]),
            updated_at=datetime.fromisoformat(row[5])
        )