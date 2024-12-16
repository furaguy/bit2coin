# src/storage/database.py
from typing import Optional, Dict, Any
import sqlite3
import json
import os
import threading

class Database:
    def __init__(self, db_path: str):
        """Initialize database connection"""
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._local = threading.local()
        self._init_db()
        
    def _get_conn(self):
        """Get thread-local database connection"""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self):
        """Initialize database tables"""
        conn = self._get_conn()
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS key_value_store (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_key 
                ON key_value_store(key)
            """)
        
    def put(self, key: str, value: Any) -> None:
        """Store a key-value pair"""
        try:
            conn = self._get_conn()
            serialized_value = json.dumps(value)
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO key_value_store (key, value) VALUES (?, ?)",
                    (key, serialized_value)
                )
        except Exception as e:
            raise DatabaseError(f"Error storing data: {str(e)}")

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value by key"""
        try:
            conn = self._get_conn()
            with conn:
                cursor = conn.execute(
                    "SELECT value FROM key_value_store WHERE key = ?",
                    (key,)
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                return json.loads(row['value'])
        except Exception as e:
            raise DatabaseError(f"Error retrieving data: {str(e)}")

    def delete(self, key: str) -> bool:
        """Delete a key-value pair"""
        try:
            conn = self._get_conn()
            with conn:
                conn.execute(
                    "DELETE FROM key_value_store WHERE key = ?",
                    (key,)
                )
            return True
        except Exception as e:
            return False

    def batch_write(self, items: Dict[str, Any]) -> bool:
        """Write multiple key-value pairs atomically"""
        try:
            conn = self._get_conn()
            with conn:
                for key, value in items.items():
                    serialized_value = json.dumps(value)
                    conn.execute(
                        "INSERT OR REPLACE INTO key_value_store (key, value) VALUES (?, ?)",
                        (key, serialized_value)
                    )
            return True
        except Exception as e:
            raise DatabaseError(f"Error in batch write: {str(e)}")

    def __iter__(self):
        """Iterate over all key-value pairs"""
        conn = self._get_conn()
        with conn:
            cursor = conn.execute("SELECT key, value FROM key_value_store")
            for row in cursor:
                yield row['key'], json.loads(row['value'])
            
    def close(self):
        """Close database connection"""
        if hasattr(self._local, 'conn'):
            self._local.conn.close()
            delattr(self._local, 'conn')

class DatabaseError(Exception):
    """Custom exception for database operations"""
    pass

# src/storage/state.py
class ChainState:
    def __init__(self, db_path: str):
        """Initialize chain state management"""
        self.db = Database(db_path)
        self._cache: Dict[str, Any] = {}
        
    def store_block(self, block_hash: str, block_data: Dict) -> bool:
        """Store a block in the database"""
        key = f"block:{block_hash}"
        try:
            self.db.put(key, block_data)
            return True
        except DatabaseError:
            return False

    def get_block(self, block_hash: str) -> Optional[Dict]:
        """Retrieve a block by its hash"""
        key = f"block:{block_hash}"
        return self.db.get(key)

    def store_transaction(self, tx_hash: str, tx_data: Dict) -> bool:
        """Store a transaction in the database"""
        key = f"tx:{tx_hash}"
        try:
            self.db.put(key, tx_data)
            return True
        except DatabaseError:
            return False

    def get_transaction(self, tx_hash: str) -> Optional[Dict]:
        """Retrieve a transaction by its hash"""
        key = f"tx:{tx_hash}"
        return self.db.get(key)

    def update_account_balance(self, address: str, balance: float) -> bool:
        """Update account balance in the database"""
        key = f"balance:{address}"
        try:
            self.db.put(key, {"balance": balance})
            return True
        except DatabaseError:
            return False

    def get_account_balance(self, address: str) -> float:
        """Get account balance from the database"""
        key = f"balance:{address}"
        data = self.db.get(key)
        return data["balance"] if data else 0.0

    def store_chain_head(self, block_hash: str) -> bool:
        """Store the current chain head hash"""
        try:
            self.db.put("chain:head", {"hash": block_hash})
            return True
        except DatabaseError:
            return False

    def get_chain_head(self) -> Optional[str]:
        """Get the current chain head hash"""
        data = self.db.get("chain:head")
        return data["hash"] if data else None

    def batch_update(self, updates: Dict[str, Any]) -> bool:
        """Perform multiple updates atomically"""
        try:
            return self.db.batch_write(updates)
        except DatabaseError:
            return False

    def close(self):
        """Close database connection"""
        if self.db:
            self.db.close()
            self.db = None