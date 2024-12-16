# src/blockchain/transaction.py
from typing import Optional, Dict, Union, TYPE_CHECKING, Any
import time
import hashlib
from dataclasses import dataclass
from enum import Enum
from decimal import Decimal
from ..crypto.signature import SignatureManager
from ..utils.config import Config

if TYPE_CHECKING:
    from .blockchain import Blockchain

class TransactionType(Enum):
    TRANSFER = "transfer"
    STAKE = "stake"
    UNSTAKE = "unstake"
    GENESIS = "genesis"  # Added for genesis transactions
    MINING_REWARD = "mining_reward"  # Added for mining rewards

@dataclass
class TransactionData:
    """Additional transaction data for special transaction types"""
    type: TransactionType
    validator_address: Optional[str] = None
    delegation_amount: Optional[Decimal] = None
    reward_share: Optional[Decimal] = None
    unbonding_time: Optional[int] = None
    genesis_message: Optional[str] = None  # Added for genesis message

class Transaction:
    def __init__(
        self, 
        sender: str, 
        recipient: str, 
        amount: Decimal, 
        transaction_type: TransactionType = TransactionType.TRANSFER,
        data: Optional[Dict[str, Any]] = None, 
        timestamp: Optional[int] = None,
        message: Optional[str] = None  # Added for genesis message
    ):
        self.sender = sender
        self.recipient = recipient
        self.amount = Decimal(str(amount))
        self.transaction_type = transaction_type
        self.timestamp = timestamp or int(time.time())
        self.message = message
        
        # Initialize transaction data
        data_dict = data or {}
        if message and transaction_type == TransactionType.GENESIS:
            data_dict['genesis_message'] = message
        self.data = TransactionData(**data_dict) if data_dict else None

        # Will be set later
        self.signature: Optional[str] = None
        self.transaction_id = self._generate_id()

    def _generate_id(self) -> str:
        """Generate unique transaction ID"""
        data = (
            f"{self.sender}{self.recipient}{str(self.amount)}"
            f"{self.timestamp}{self.transaction_type.value}"
            f"{self.message or ''}"
        )
        if self.data:
            data += str(self.data.__dict__)
        return hashlib.sha256(data.encode()).hexdigest()

    def set_signature(self, signature: str):
        """Set transaction signature"""
        self.signature = signature

    def verify_signature(self, public_key: str) -> bool:
        """Verify transaction signature"""
        # Genesis and mining reward transactions don't need signatures
        if self.transaction_type in [TransactionType.GENESIS, TransactionType.MINING_REWARD]:
            return True
            
        if not self.signature:
            return False
            
        message = self.to_string()
        return SignatureManager.verify_data(message, self.signature, public_key)

    def verify_transaction(self, blockchain: 'Blockchain') -> bool:
        """Comprehensive transaction verification"""
        try:
            # Genesis transactions are always valid
            if self.transaction_type == TransactionType.GENESIS:
                return True

            # Basic validation
            if not self._verify_basic_fields():
                return False

            # Verify unspendable coins can't be spent
            if blockchain.is_unspendable_address(self.sender):
                return False

            # Verify transaction type specific rules
            if not self._verify_transaction_type(blockchain):
                return False

            # Verify sender has sufficient balance
            if not self._verify_balance(blockchain):
                return False

            return True

        except Exception:
            return False

    def _verify_basic_fields(self) -> bool:
        """Verify basic transaction fields"""
        return (
            isinstance(self.sender, str) and
            isinstance(self.recipient, str) and
            isinstance(self.amount, Decimal) and
            self.amount >= 0 and
            isinstance(self.timestamp, int) and
            self.timestamp <= int(time.time()) + 300  # Not more than 5 mins in future
        )

    def _verify_transaction_type(self, blockchain: 'Blockchain') -> bool:
        """Verify transaction based on its type"""
        if self.transaction_type == TransactionType.TRANSFER:
            return True
        elif self.transaction_type == TransactionType.MINING_REWARD:
            return self._verify_mining_reward(blockchain)
        return False

    def _verify_mining_reward(self, blockchain: 'Blockchain') -> bool:
        """Verify mining reward transaction"""
        if self.sender != "0":  # Mining rewards must come from system
            return False
        
        # Verify reward amount matches current block reward
        current_height = len(blockchain.chain)
        expected_reward = blockchain.get_block_reward(current_height)
        return self.amount == expected_reward

    def _verify_balance(self, blockchain: 'Blockchain') -> bool:
        """Verify sender has sufficient balance"""
        if self.transaction_type in [TransactionType.GENESIS, TransactionType.MINING_REWARD]:
            return True
            
        sender_balance = blockchain.get_balance(self.sender)
        return sender_balance >= self.amount

    def to_dict(self) -> Dict:
        """Convert transaction to dictionary"""
        return {
            "transaction_id": self.transaction_id,
            "sender": self.sender,
            "recipient": self.recipient,
            "amount": str(self.amount),
            "timestamp": self.timestamp,
            "type": self.transaction_type.value,
            "data": self.data.__dict__ if self.data else None,
            "message": self.message,
            "signature": self.signature
        }

    def to_string(self) -> str:
        """Convert transaction to string for signing"""
        return (
            f"{self.sender}{self.recipient}{str(self.amount)}"
            f"{self.timestamp}{self.transaction_type.value}"
            f"{self.message or ''}"
            f"{str(self.data.__dict__) if self.data else ''}"
        )