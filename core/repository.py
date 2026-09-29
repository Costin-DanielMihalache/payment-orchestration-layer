import sqlite3
from core.transaction import Transaction
from core.status import Status
from datetime import datetime
from core.database import Database

class ConcurrentModificationError(Exception):
    # Raised by save() when the row was changed by someone else since this
    # Transaction object was loaded (optimistic locking, see save()). The
    # caller must reload the transaction and decide again - never retry the
    # same stale object blindly.
    pass

class TransactionRepository:
    def __init__(self, db_path="transactions.db", db: Database | None = None):
        # Pass the same Database to every repository/store that must take part
        # in one atomic transaction; db_path is only used when none is given
        self.db = db if db is not None else Database(db_path)
        self._create_table()

    def _create_table(self):
        with self.db.transaction() as connection:
            connection.execute("""
                               CREATE TABLE IF NOT EXISTS transactions
                               (
                                   transaction_id TEXT PRIMARY KEY,
                                   amount INTEGER NOT NULL,
                                   currency TEXT,
                                   status TEXT,
                                   created_at TEXT,
                                   updated_at TEXT,
                                   version INTEGER NOT NULL DEFAULT 1
                               )
                               """)
            # Databases created before optimistic locking have no version
            # column - add it (existing rows count as version 1)
            columns = [row[1] for row in connection.execute("PRAGMA table_info(transactions)")]
            if "version" not in columns:
                connection.execute("ALTER TABLE transactions ADD COLUMN version INTEGER NOT NULL DEFAULT 1")

    def save(self, transaction: Transaction):
        # Optimistic locking (h): transaction.version is the version of the row
        # this object was loaded from (0 = never saved). We don't lock the row
        # while the object lives in memory - we only check, at write time, that
        # nobody else changed it in the meantime:
        #   UPDATE ... WHERE transaction_id=? AND version=<the one we loaded>
        # If 0 rows match, someone else saved first, and instead of silently
        # overwriting their change (lost update) we raise.
        # Every call still saves the full current state (not just the changed
        # fields) and keeps no history of transitions, only the latest state.
        with self.db.transaction() as connection:
            if transaction.version == 0:
                try:
                    connection.execute(
                        "INSERT INTO transactions (transaction_id,amount,currency,status,created_at,updated_at,version) VALUES (?,?,?,?,?,?,1)",
                        (transaction.transaction_id, transaction.amount, transaction.currency, transaction.status.value,
                         transaction.created_at.isoformat(), transaction.updated_at.isoformat())
                    )
                except sqlite3.IntegrityError:
                    raise ConcurrentModificationError(f"Transaction {transaction.transaction_id} already exists")
                new_version = 1
            else:
                new_version = transaction.version + 1
                cursor = connection.execute(
                    "UPDATE transactions SET amount=?,currency=?,status=?,updated_at=?,version=? WHERE transaction_id=? AND version=?",
                    (transaction.amount, transaction.currency, transaction.status.value,
                     transaction.updated_at.isoformat(), new_version, transaction.transaction_id, transaction.version)
                )
                if cursor.rowcount != 1:
                    raise ConcurrentModificationError(
                        f"Transaction {transaction.transaction_id} was modified by someone else (expected version {transaction.version})")
        # Only after the write went through. If this save() was part of a
        # bigger transaction() block that later rolls back, this object is
        # ahead of the database - reload it before saving again.
        transaction.version = new_version

    def get(self, transaction_id: str) -> Transaction | None:
        row = self.db.fetchone(
            "SELECT transaction_id,amount,currency,status,created_at,updated_at,version FROM transactions WHERE transaction_id=?",
            (transaction_id,)
        )
        if row is None:
            return None
        return Transaction.from_row(
            transaction_id=row[0],
            # int(): databases created before amount became INTEGER still
            # hold floats (1050.0) - always hand back minor units as int
            amount=int(row[1]),
            currency=row[2],
            status=Status(row[3]),
            created_at=datetime.fromisoformat(row[4]),
            updated_at=datetime.fromisoformat(row[5]),
            version=row[6]
        )