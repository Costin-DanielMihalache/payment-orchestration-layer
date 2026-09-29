import sqlite3

class IdempotencyStore:
    def __init__(self,db_path="transactions.db"):
        self.connection=sqlite3.connect(db_path,check_same_thread=False)
        self._create_table()

    def _create_table(self):
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS idempotency_keys (
                idempotency_key TEXT PRIMARY KEY,
                fingerprint TEXT NOT NULL,
                transaction_id TEXT NOT NULL
            )
        """)
        self.connection.commit()

    def reserve(self,key:str,fingerprint:str,transaction_id:str) -> tuple[str,str] | None:
        # The PRIMARY KEY makes check-and-insert atomic: if two requests with
        # the same key arrive at the same time, exactly one INSERT succeeds.
        # Returns None if the key was reserved now, or (transaction_id,
        # fingerprint) of the request that reserved it earlier.
        try:
            self.connection.execute(
                "INSERT INTO idempotency_keys (idempotency_key,fingerprint,transaction_id) VALUES (?,?,?)",
                (key,fingerprint,transaction_id)
            )
            self.connection.commit()
            return None
        except sqlite3.IntegrityError:
            row=self.connection.execute(
                "SELECT transaction_id,fingerprint FROM idempotency_keys WHERE idempotency_key=?",
                (key,)
            ).fetchone()
            return (row[0],row[1])