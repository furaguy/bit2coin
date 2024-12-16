# src/blockchain/block.py
from typing import List, Optional, Dict
from dataclasses import dataclass
import time
import hashlib
import json
from decimal import Decimal
from .transaction import Transaction

@dataclass
class BlockHeader:
    version: int
    previous_hash: str
    merkle_root: str
    timestamp: int
    height: int
    validator: Optional[str]

class Block:
    def __init__(
        self,
        height: int,
        previous_hash: str,
        transactions: List[Transaction],
        timestamp: Optional[int] = None,
        validator: Optional[str] = None,
        version: int = 1
    ):
        self.height = height
        self.previous_hash = previous_hash
        self.transactions = transactions
        self.timestamp = timestamp or int(time.time())
        self.validator = validator
        self.version = version
        
        # Computed properties
        self.merkle_root = self._calculate_merkle_root()
        self.header = BlockHeader(
            version=self.version,
            previous_hash=self.previous_hash,
            merkle_root=self.merkle_root,
            timestamp=self.timestamp,
            height=self.height,
            validator=self.validator
        )
        self.hash = self._calculate_hash()
        self.size = self._calculate_size()

    def _calculate_merkle_root(self) -> str:
        """Calculate Merkle root of transactions"""
        if not self.transactions:
            return hashlib.sha256(b'').hexdigest()
            
        transaction_hashes = [tx.transaction_id for tx in self.transactions]
        while len(transaction_hashes) > 1:
            if len(transaction_hashes) % 2 != 0:
                transaction_hashes.append(transaction_hashes[-1])
            
            next_level = []
            for i in range(0, len(transaction_hashes), 2):
                combined = transaction_hashes[i] + transaction_hashes[i+1]
                next_hash = hashlib.sha256(combined.encode()).hexdigest()
                next_level.append(next_hash)
            
            transaction_hashes = next_level
            
        return transaction_hashes[0]

    def _calculate_hash(self) -> str:
        """Calculate block hash"""
        header_dict = {
            "version": self.version,
            "previous_hash": self.previous_hash,
            "merkle_root": self.merkle_root,
            "timestamp": self.timestamp,
            "height": self.height,
            "validator": self.validator
        }
        header_string = json.dumps(header_dict, sort_keys=True)
        return hashlib.sha256(header_string.encode()).hexdigest()

    def _calculate_size(self) -> int:
        """Calculate block size in bytes"""
        return sum(len(str(tx.to_dict())) for tx in self.transactions)

    def add_transaction(self, transaction: Transaction) -> bool:
        """Add transaction to block if valid"""
        # Genesis block can only contain genesis transactions
        if self.height == 0 and transaction.transaction_type != "genesis":
            return False
            
        # Check block size limit
        if self._calculate_size() + len(str(transaction.to_dict())) > 1_000_000:  # 1MB limit
            return False
            
        self.transactions.append(transaction)
        self.merkle_root = self._calculate_merkle_root()
        self.hash = self._calculate_hash()
        self.size = self._calculate_size()
        return True

    def verify_block(self) -> bool:
        """Verify block integrity"""
        # Verify block hash
        if self._calculate_hash() != self.hash:
            return False
            
        # Verify merkle root
        if self._calculate_merkle_root() != self.merkle_root:
            return False
            
        # Verify timestamp
        if self.timestamp > int(time.time()) + 7200:  # No more than 2 hours in future
            return False
            
        # Verify transactions
        for tx in self.transactions:
            if not tx.verify_transaction():
                return False
                
        return True

    def get_transaction(self, tx_id: str) -> Optional[Transaction]:
        """Get transaction by ID"""
        for tx in self.transactions:
            if tx.transaction_id == tx_id:
                return tx
        return None

    def to_dict(self) -> Dict:
        """Convert block to dictionary"""
        return {
            "height": self.height,
            "previous_hash": self.previous_hash,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "timestamp": self.timestamp,
            "validator": self.validator,
            "version": self.version,
            "merkle_root": self.merkle_root,
            "hash": self.hash,
            "size": self.size
        }

    @staticmethod
    def from_dict(data: Dict) -> 'Block':
        """Create block from dictionary"""
        transactions = [Transaction.from_dict(tx) for tx in data["transactions"]]
        block = Block(
            height=data["height"],
            previous_hash=data["previous_hash"],
            transactions=transactions,
            timestamp=data["timestamp"],
            validator=data["validator"],
            version=data["version"]
        )
        return block