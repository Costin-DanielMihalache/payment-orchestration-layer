import sqlite3
from core.database import Database

class IdempotencyStore:
    def __init__(self, db_path="transactions.db", db: Database | None = None):
        self.db = db if db is not None else Database(db_path)
        self._create_table()

    def _create_table(self):
        with self.db.transaction() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS idempotency_keys (
                    idempotency_key TEXT PRIMARY KEY,
                    fingerprint TEXT NOT NULL,
                    transaction_id TEXT NOT NULL
                )
            """)

    def reserve(self, key: str, fingerprint: str, transaction_id: str) -> tuple[str, str] | None:
        # The PRIMARY KEY makes check-and-insert atomic: if two requests with
        # the same key arrive at the same time, exactly one INSERT succeeds.
        # Returns None if the key was reserved now, or (transaction_id,
        # fingerprint) of the request that reserved it earlier.
        # If called inside an outer db.transaction() block (as api.py does, to
        # reserve the key and save the transaction together), the reservation
        # is only committed when that whole block succeeds.
        try:
            with self.db.transaction() as connection:
                connection.execute(
                    "INSERT INTO idempotency_keys (idempotency_key,fingerprint,transaction_id) VALUES (?,?,?)",
                    (key, fingerprint, transaction_id)
                )
            return None
        except sqlite3.IntegrityError:
            row = self.db.fetchone(
                "SELECT transaction_id,fingerprint FROM idempotency_keys WHERE idempotency_key=?",
                (key,)
            )
            return (row[0], row[1])