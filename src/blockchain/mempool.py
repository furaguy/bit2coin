# src/blockchain/mempool.py
from typing import List, Dict, Set
import time
from decimal import Decimal
from collections import OrderedDict
from .transaction import Transaction
from ..utils.config import Config

class Mempool:
    def __init__(self, blockchain=None):  # Type hint omitted to avoid circular import
        self.blockchain = blockchain
        self.transactions: OrderedDict[str, Transaction] = OrderedDict()
        self.transaction_fees: Dict[str, Decimal] = {}  # tx_id -> fee
        self.sender_transactions: Dict[str, Set[str]] = {}  # sender -> tx_ids
        
        # Configuration
        self.max_size = 5000  # Maximum number of transactions
        self.max_age = 72 * 3600  # 72 hours in seconds
        self.min_fee_rate = Decimal('0.00001')  # Minimum fee per byte

    def add_transaction(self, transaction: Transaction) -> bool:
        """Add transaction to mempool"""
        # Basic validation
        if not self._validate_transaction(transaction):
            return False
            
        # Check if transaction already exists
        if transaction.transaction_id in self.transactions:
            return False
            
        # Check mempool size limit
        if len(self.transactions) >= self.max_size:
            self._remove_lowest_fee_transaction()
            
        # Add transaction
        self.transactions[transaction.transaction_id] = transaction
        
        # Track sender's transactions
        if transaction.sender not in self.sender_transactions:
            self.sender_transactions[transaction.sender] = set()
        self.sender_transactions[transaction.sender].add(transaction.transaction_id)
        
        # Calculate and store fee
        fee = self._calculate_transaction_fee(transaction)
        self.transaction_fees[transaction.transaction_id] = fee
        
        return True

    def _validate_transaction(self, transaction: Transaction) -> bool:
        """Validate transaction for mempool acceptance"""
        # Check if blockchain reference exists
        if not self.blockchain:
            return False
            
        # Don't accept transactions from unspendable address
        if self.blockchain.is_unspendable_address(transaction.sender):
            return False
            
        # Check if transaction is too old
        if int(time.time()) - transaction.timestamp > self.max_age:
            return False
            
        # Verify transaction signature and balance
        if not transaction.verify_transaction(self.blockchain):
            return False
            
        # Check minimum fee rate
        fee = self._calculate_transaction_fee(transaction)
        if fee / len(str(transaction.to_dict())) < self.min_fee_rate:
            return False
            
        return True

    def _calculate_transaction_fee(self, transaction: Transaction) -> Decimal:
        """Calculate transaction fee"""
        # For now, using simple fixed fee
        # Could be enhanced with more sophisticated fee calculation
        return Decimal('0.0001')

    def _remove_lowest_fee_transaction(self):
        """Remove transaction with lowest fee when mempool is full"""
        if not self.transactions:
            return
            
        lowest_fee_tx_id = min(
            self.transaction_fees.items(),
            key=lambda x: x[1]
        )[0]
        
        self._remove_transaction(lowest_fee_tx_id)

    def _remove_transaction(self, tx_id: str):
        """Remove transaction from mempool"""
        if tx_id not in self.transactions:
            return
            
        transaction = self.transactions[tx_id]
        
        # Remove from main storage
        del self.transactions[tx_id]
        del self.transaction_fees[tx_id]
        
        # Remove from sender tracking
        if transaction.sender in self.sender_transactions:
            self.sender_transactions[transaction.sender].remove(tx_id)
            if not self.sender_transactions[transaction.sender]:
                del self.sender_transactions[transaction.sender]

    def get_transactions(self, limit: int = 100) -> List[Transaction]:
        """Get transactions for new block, ordered by fee"""
        sorted_txs = sorted(
            self.transactions.values(),
            key=lambda tx: self.transaction_fees[tx.transaction_id],
            reverse=True
        )
        return sorted_txs[:limit]

    def remove_transactions(self, transaction_ids: List[str]):
        """Remove transactions that were included in a block"""
        for tx_id in transaction_ids:
            self._remove_transaction(tx_id)

    def clear_expired(self):
        """Remove expired transactions"""
        current_time = int(time.time())
        expired = [
            tx_id for tx_id, tx in self.transactions.items()
            if current_time - tx.timestamp > self.max_age
        ]
        for tx_id in expired:
            self._remove_transaction(tx_id)

    def get_transaction(self, tx_id: str) -> Transaction:
        """Get specific transaction from mempool"""
        return self.transactions.get(tx_id)

    def has_transaction(self, tx_id: str) -> bool:
        """Check if transaction exists in mempool"""
        return tx_id in self.transactions

    def get_sender_transactions(self, sender: str) -> List[Transaction]:
        """Get all transactions from specific sender"""
        if sender not in self.sender_transactions:
            return []
        return [
            self.transactions[tx_id]
            for tx_id in self.sender_transactions[sender]
        ]

    def get_mempool_size(self) -> int:
        """Get current size of mempool"""
        return len(self.transactions)

    def get_mempool_stats(self) -> Dict:
        """Get mempool statistics"""
        return {
            "size": len(self.transactions),
            "total_fees": sum(self.transaction_fees.values()),
            "unique_senders": len(self.sender_transactions),
            "oldest_transaction": min(
                (tx.timestamp for tx in self.transactions.values()),
                default=0
            )
        }