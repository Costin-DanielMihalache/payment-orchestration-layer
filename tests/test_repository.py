from core.repository import TransactionRepository
from core.transaction import Transaction
from core.status import Status
from datetime import datetime
from core.database import Database

def test_save_and_get_returns_identical_transaction():
    repo=TransactionRepository(db_path=":memory:")

    t=Transaction(200,"RON")
    t.change_status(Status.PROCESSING,delay=0)
    repo.save(t)

    loaded=repo.get(t.transaction_id)

    assert loaded is not None
    assert loaded.transaction_id==t.transaction_id
    assert loaded.amount==t.amount
    assert loaded.currency==t.currency
    assert loaded.status==t.status
    assert loaded.created_at==t.created_at
    assert loaded.updated_at==t.updated_at

def test_get_returns_none_for_missing_transaction():
    repo=TransactionRepository(db_path=":memory:")

    result=repo.get("id-inexistent")

    assert result is None

def test_amount_is_stored_and_returned_as_int():
    repo=TransactionRepository(db_path=":memory:")
    t=Transaction(1050,"EUR")
    repo.save(t)

    loaded=repo.get(t.transaction_id)

    assert type(loaded.amount) is int
    assert loaded.amount==1050


def test_amount_from_an_old_database_with_real_column_is_returned_as_int():
    db=Database(":memory:")
    with db.transaction() as connection:
        connection.execute("""
            CREATE TABLE transactions (
                transaction_id TEXT PRIMARY KEY,
                amount REAL,
                currency TEXT,
                status TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        now=datetime.now().isoformat()
        connection.execute(
            "INSERT INTO transactions VALUES (?,?,?,?,?,?)",
            ("old-1",1050,"EUR","PROCESSING",now,now)
        )

    loaded=TransactionRepository(db=db).get("old-1")

    assert type(loaded.amount) is int
    assert loaded.amount==1050