import sqlite3
import threading
from contextlib import contextmanager


class Database:
    # One SQLite connection shared by every repository/store (g: atomicity).
    # With a separate connection per class, two related writes (e.g. "mark
    # webhook processed" + "save new status") were two independent commits:
    # a crash between them left the data inconsistent. Sharing one connection
    # lets us group them in a single transaction() block: all or nothing.
    def __init__(self,db_path="transactions.db"):
        self.connection=sqlite3.connect(db_path,check_same_thread=False)
        # FastAPI runs sync endpoints in a thread pool, and all threads share
        # this one connection - without the lock, thread A's rollback would
        # also undo thread B's half-finished writes. RLock = same thread may
        # re-enter (nested transaction() blocks).
        self._lock=threading.RLock()
        self._depth=0

    @contextmanager
    def transaction(self):
        # Usage: with db.transaction() as connection: connection.execute(...)
        # Commits when the block ends normally, rolls back if it raises.
        # Nested blocks join the outer one: only the outermost commits, so a
        # repository's own save() is atomic on its own AND can be grouped
        # with other writes by an outer block.
        # Note: if an inner block raises and the caller catches it without
        # re-raising, the outer block still commits what was written so far.
        with self._lock:
            outermost=self._depth==0
            self._depth+=1
            try:
                yield self.connection
                if outermost:
                    self.connection.commit()
            except BaseException:
                if outermost:
                    self.connection.rollback()
                raise
            finally:
                self._depth-=1

    def fetchone(self,sql,params=()):
        # Reads also take the lock: on a shared connection a SELECT would
        # otherwise see another thread's uncommitted writes
        with self._lock:
            return self.connection.execute(sql,params).fetchone()