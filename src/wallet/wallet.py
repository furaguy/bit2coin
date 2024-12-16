# src/wallet/wallet.py
from typing import Optional, List, Dict
from decimal import Decimal
import time
from ..crypto.signature import SignatureManager
from ..blockchain.transaction import Transaction, TransactionType
from ..utils.config import Config

class Wallet:
    def __init__(
        self,
        private_key: Optional[str] = None,
        blockchain = None  # Type hint omitted to avoid circular import
    ):
        self.signature_manager = SignatureManager(private_key)
        self.address = self.signature_manager.get_address()
        self.blockchain = blockchain
        self.transactions: List[Transaction] = []
        self.nonce = 0

    @classmethod
    def generate_new(cls) -> 'Wallet':
        """Generate new wallet with random private key"""
        return cls()

    def get_balance(self) -> Decimal:
        """Get wallet balance"""
        if not self.blockchain:
            return Decimal('0')
        return self.blockchain.get_balance(self.address)

    def create_transaction(
        self,
        recipient: str,
        amount: Decimal,
        transaction_type: TransactionType = TransactionType.TRANSFER,
        data: Optional[Dict] = None
    ) -> Optional[Transaction]:
        """Create new transaction"""
        if not self.blockchain:
            return None
            
        # Check if we're the unspendable genesis address
        if self.is_unspendable():
            return None
            
        # Verify sufficient balance
        balance = self.get_balance()
        if balance < amount:
            return None
            
        # Create transaction
        transaction = Transaction(
            sender=self.address,
            recipient=recipient,
            amount=amount,
            transaction_type=transaction_type,
            data=data,
            timestamp=int(time.time())
        )
        
        # Sign transaction
        signature = self.signature_manager.sign_data(transaction.to_string())
        transaction.set_signature(signature)
        
        self.transactions.append(transaction)
        return transaction

    def stake_tokens(self, amount: Decimal) -> Optional[Transaction]:
        """Create staking transaction"""
        if amount < Config.MINIMUM_STAKE:
            return None
            
        return self.create_transaction(
            recipient=self.address,
            amount=amount,
            transaction_type=TransactionType.STAKE,
            data={"validator_address": self.address}
        )

    def claim_rewards(self) -> Optional[Transaction]:
        """Claim staking rewards"""
        if not self.blockchain:
            return None
            
        unclaimed_rewards = self.blockchain.get_unclaimed_rewards(self.address)
        if unclaimed_rewards <= 0:
            return None
            
        return self.create_transaction(
            recipient=self.address,
            amount=Decimal('0'),
            transaction_type=TransactionType.CLAIM_REWARDS
        )

    def is_unspendable(self) -> bool:
        """Check if this is the unspendable genesis wallet"""
        if not self.blockchain:
            return False
        return self.blockchain.is_unspendable_address(self.address)

    def is_staking_wallet(self) -> bool:
        """Check if this is the genesis staking wallet"""
        if not self.blockchain:
            return False
        return self.blockchain.is_staking_address(self.address)

    def get_transaction_history(self) -> List[Transaction]:
        """Get wallet transaction history"""
        return self.transactions.copy()

    def to_dict(self) -> Dict:
        """Convert wallet to dictionary"""
        return {
            "address": self.address,
            "balance": str(self.get_balance()),
            "transactions": len(self.transactions),
            "is_staking": self.is_staking_wallet(),
            "is_unspendable": self.is_unspendable()
        }