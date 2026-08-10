from core.repository import TransactionRepository
from core.transaction import Transaction
from core.status import Status

def test_save_and_get_returns_identical_transaction():
    repo=TransactionRepository(db_path=":memory:")

    t=Transaction(200,"LEU")
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