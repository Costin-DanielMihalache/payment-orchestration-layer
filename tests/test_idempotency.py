from core.idempotency import IdempotencyStore

def test_first_reserve_succeeds_and_second_returns_original():
    store=IdempotencyStore(db_path=":memory:")

    assert store.reserve("k1","1000:EUR","tx-1") is None
    assert store.reserve("k1","1000:EUR","tx-2")==("tx-1","1000:EUR")