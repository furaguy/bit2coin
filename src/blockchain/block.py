# src/blockchain/block.py
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import time
import hashlib
import json
from decimal import Decimal
import logging

from .transaction import Transaction, TransactionType
from ..utils.config import Config

logger = logging.getLogger(__name__)

@dataclass
class BlockHeader:
    """Block header structure"""
    version: int
    previous_hash: str
    merkle_root: str
    timestamp: int
    height: int
    validator: Optional[str]
    difficulty: int
    nonce: int

class BlockError(Exception):
    """Base exception for block-related errors"""
    pass

class Block:
    VERSION = 1
    MAX_SIZE = 1_048_576  # 1MB in bytes
    MAX_TRANSACTIONS = 2000
    
    def __init__(
        self,
        height: int,
        previous_hash: str,
        transactions: List[Transaction],
        timestamp: Optional[int] = None,
        validator: Optional[str] = None,
        version: int = VERSION,
        difficulty: int = 1,
        nonce: int = 0
    ):
        """Initialize block with given parameters"""
        self.height = height
        self.previous_hash = previous_hash
        self.transactions = transactions
        self.timestamp = timestamp or int(time.time())
        self.validator = validator
        self.version = version
        self.difficulty = difficulty
        self.nonce = nonce
        
        # Computed properties
        self.merkle_root = self._calculate_merkle_root()
        self.header = BlockHeader(
            version=self.version,
            previous_hash=self.previous_hash,
            merkle_root=self.merkle_root,
            timestamp=self.timestamp,
            height=self.height,
            validator=self.validator,
            difficulty=self.difficulty,
            nonce=self.nonce
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
            "validator": self.validator,
            "difficulty": self.difficulty,
            "nonce": self.nonce
        }
        header_string = json.dumps(header_dict, sort_keys=True)
        return hashlib.sha256(header_string.encode()).hexdigest()

    def _calculate_size(self) -> int:
        """Calculate block size in bytes"""
        # Header size
        size = len(json.dumps(self.header.__dict__).encode())
        # Transactions size
        size += sum(len(json.dumps(tx.to_dict()).encode()) for tx in self.transactions)
        return size

    def add_transaction(self, transaction: Transaction) -> bool:
        """Add transaction to block if valid"""
        try:
            # Check block size limit
            potential_size = self.size + len(json.dumps(transaction.to_dict()).encode())
            if potential_size > self.MAX_SIZE:
                logger.warning(f"Adding transaction would exceed block size limit: {potential_size} > {self.MAX_SIZE}")
                return False
                
            # Check transaction limit
            if len(self.transactions) >= self.MAX_TRANSACTIONS:
                logger.warning(f"Block has reached maximum transaction limit: {self.MAX_TRANSACTIONS}")
                return False

            # Special rules for genesis block
            if self.height == 0 and transaction.transaction_type != TransactionType.GENESIS:
                logger.warning("Only genesis transactions allowed in genesis block")
                return False
            
            self.transactions.append(transaction)
            # Update block properties
            self.merkle_root = self._calculate_merkle_root()
            self.hash = self._calculate_hash()
            self.size = self._calculate_size()
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding transaction: {str(e)}")
            return False

    def verify_block(self) -> bool:
        """Verify block integrity"""
        try:
            # Verify block hash
            if self._calculate_hash() != self.hash:
                logger.warning("Block hash verification failed")
                return False
                
            # Verify merkle root
            if self._calculate_merkle_root() != self.merkle_root:
                logger.warning("Merkle root verification failed")
                return False
                
            # Verify timestamp
            if self.timestamp > int(time.time()) + 7200:  # No more than 2 hours in future
                logger.warning(f"Block timestamp too far in future: {self.timestamp}")
                return False
                
            # Verify block size
            if self.size > self.MAX_SIZE:
                logger.warning(f"Block size exceeds maximum: {self.size} > {self.MAX_SIZE}")
                return False

            # Verify transaction count
            if len(self.transactions) > self.MAX_TRANSACTIONS:
                logger.warning(f"Block exceeds maximum transactions: {len(self.transactions)} > {self.MAX_TRANSACTIONS}")
                return False
                
            # Verify transactions
            for tx in self.transactions:
                if not tx.verify_transaction(None):  # Basic transaction verification
                    logger.warning(f"Transaction verification failed: {tx.transaction_id}")
                    return False

            # Verify reward transaction if not genesis block
            if self.height > 0:
                reward_tx = self._get_reward_transaction()
                if not reward_tx:
                    logger.warning("No reward transaction found in non-genesis block")
                    return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error verifying block: {str(e)}")
            return False

    def _get_reward_transaction(self) -> Optional[Transaction]:
        """Get the reward transaction if present"""
        for tx in self.transactions:
            if tx.transaction_type == TransactionType.MINING_REWARD:
                return tx
        return None

    def get_transaction(self, tx_id: str) -> Optional[Transaction]:
        """Get transaction by ID"""
        for tx in self.transactions:
            if tx.transaction_id == tx_id:
                return tx
        return None

    def get_transaction_count(self) -> Dict[str, int]:
        """Get transaction count by type"""
        counts = {}
        for tx in self.transactions:
            tx_type = tx.transaction_type.value
            counts[tx_type] = counts.get(tx_type, 0) + 1
        return counts

    def calculate_fees(self) -> Decimal:
        """Calculate total transaction fees"""
        return sum(
            tx.fee for tx in self.transactions 
            if tx.transaction_type not in [TransactionType.GENESIS, TransactionType.MINING_REWARD]
        )

    def to_dict(self) -> Dict[str, Any]:
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
            "size": self.size,
            "difficulty": self.difficulty,
            "nonce": self.nonce
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Block':
        """Create block from dictionary"""
        transactions = [Transaction.from_dict(tx) for tx in data["transactions"]]
        block = cls(
            height=data["height"],
            previous_hash=data["previous_hash"],
            transactions=transactions,
            timestamp=data["timestamp"],
            validator=data["validator"],
            version=data.get("version", cls.VERSION),
            difficulty=data.get("difficulty", 1),
            nonce=data.get("nonce", 0)
        )
        
        # Verify the hash matches
        if block.hash != data["hash"]:
            raise BlockError("Block hash mismatch")
            
        return block

    def __str__(self) -> str:
        """String representation of block"""
        return (
            f"Block(height={self.height}, "
            f"hash={self.hash[:8]}..., "
            f"tx_count={len(self.transactions)}, "
            f"size={self.size})"
        )

    def __eq__(self, other: object) -> bool:
        """Compare two blocks"""
        if not isinstance(other, Block):
            return NotImplemented
        return self.hash == other.hash