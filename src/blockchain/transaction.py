# src/blockchain/transaction.py
from typing import Optional, Dict, Union, TYPE_CHECKING, Any
import time
import hashlib
from dataclasses import dataclass
from enum import Enum
from decimal import Decimal
import logging

if TYPE_CHECKING:
    from .blockchain import Blockchain

from ..crypto.signature import SignatureManager
from ..utils.config import Config

logger = logging.getLogger(__name__)

class TransactionType(Enum):
    TRANSFER = "transfer"
    STAKE = "stake"
    UNSTAKE = "unstake"
    GENESIS = "genesis"
    MINING_REWARD = "mining_reward"
    DELEGATE = "delegate"
    UNDELEGATE = "undelegate"
    CLAIM_REWARD = "claim_reward"

@dataclass
class TransactionData:
    """Additional transaction data for special transaction types"""
    type: TransactionType
    validator_address: Optional[str] = None
    delegation_amount: Optional[Decimal] = None
    reward_share: Optional[Decimal] = None
    unbonding_time: Optional[int] = None
    genesis_message: Optional[str] = None
    nonce: Optional[int] = None

@dataclass
class TransactionStatus:
    is_valid: bool
    in_mempool: bool
    confirmations: int
    error: Optional[str] = None
    block_height: Optional[int] = None
    block_hash: Optional[str] = None

class TransactionError(Exception):
    """Base class for transaction-related errors"""
    pass

class Transaction:
    VERSION = 1
    MAX_SIZE = 100_000  # 100KB limit
    MAX_FUTURE_TIME = 7200  # 2 hours
    MAX_PAST_TIME = 86400  # 24 hours
    BASE_FEE = Decimal('0.0001')
    SIZE_FEE_RATE = Decimal('0.000001')

    def __init__(
        self, 
        sender: str, 
        recipient: str, 
        amount: float, 
        transaction_type: Union[TransactionType, str] = TransactionType.TRANSFER,
        data: Optional[Dict[str, Any]] = None, 
        timestamp: Optional[int] = None,
        message: Optional[str] = None,
        version: int = VERSION,
        nonce: Optional[int] = None
    ):
        """Initialize transaction with given parameters"""
        self.version = version
        self.sender = sender
        self.recipient = recipient
        self.amount = Decimal(str(amount))
        
        # Handle transaction type
        if isinstance(transaction_type, str):
            try:
                self.transaction_type = TransactionType[transaction_type.upper()]
            except KeyError:
                self.transaction_type = TransactionType.TRANSFER
        else:
            self.transaction_type = transaction_type

        self.timestamp = timestamp or int(time.time())
        self.message = message
        self.nonce = nonce or 0
        self.signature: Optional[str] = None

        # Initialize transaction data
        data_dict = data or {}
        if message and transaction_type == TransactionType.GENESIS:
            data_dict['genesis_message'] = message
        data_dict['type'] = self.transaction_type
        data_dict['nonce'] = self.nonce
            
        self.data = TransactionData(**data_dict) if data_dict else None
        
        # Generate transaction ID
        self.transaction_id = self._generate_id()

    def _generate_id(self) -> str:
        """Generate unique transaction ID"""
        data = (
            f"{self.sender}{self.recipient}{str(self.amount)}"
            f"{self.timestamp}{self.transaction_type.value}"
            f"{self.message or ''}{self.nonce}"
            f"{self.version}"
        )
        if self.data:
            data += str(self.data.__dict__)
        return hashlib.sha256(data.encode()).hexdigest()

    @property
    def fee(self) -> Decimal:
        """Get transaction fee"""
        if self.transaction_type in [TransactionType.GENESIS, TransactionType.MINING_REWARD]:
            return Decimal('0')
        return self._calculate_fee()

    def _calculate_fee(self) -> Decimal:
        """Calculate transaction fee based on size and type"""
        size_fee = Decimal(len(self.to_string())) * self.SIZE_FEE_RATE
        return self.BASE_FEE + size_fee

    def set_signature(self, signature: str):
        """Set transaction signature"""
        self.signature = signature
        logger.debug(f"Set signature for transaction {self.transaction_id}: {signature[:32]}...")

    def verify_signature(self, public_key: str) -> bool:
        """Verify transaction signature"""
        logger.debug(f"Verifying signature for transaction {self.transaction_id}")
        
        if self.transaction_type in [TransactionType.GENESIS, TransactionType.MINING_REWARD]:
            logger.debug("Genesis/Mining reward transaction - no signature needed")
            return True
            
        if not self.signature:
            logger.warning("Transaction has no signature")
            return False
            
        message = self.to_string()
        return SignatureManager.verify_signature(message, self.signature, public_key)

    def is_valid(self, blockchain: 'Blockchain') -> bool:
        """Alias for verify_transaction for compatibility"""
        return self.verify_transaction(blockchain)

    def verify_transaction(self, blockchain: 'Blockchain') -> bool:
        """Comprehensive transaction verification"""
        try:
            logger.debug(f"Verifying transaction {self.transaction_id}")
            logger.debug(f"Type: {self.transaction_type}")
            logger.debug(f"Sender: {self.sender}")
            logger.debug(f"Recipient: {self.recipient}")
            logger.debug(f"Amount: {self.amount}")
            
            # Genesis transactions are always valid
            if self.transaction_type == TransactionType.GENESIS:
                logger.debug("Genesis transaction - automatically valid")
                return True

            # Perform all validations
            validations = [
                self._verify_basic_fields(),
                self._verify_size(),
                self._verify_timestamp(),
                self._verify_transaction_data(),
                not blockchain.is_unspendable_address(self.sender),
                self._verify_transaction_type(blockchain),
                self._verify_balance(blockchain)
            ]

            if not all(validations):
                logger.warning("Transaction validation failed")
                return False

            logger.debug("Transaction verification successful")
            return True

        except Exception as e:
            logger.error(f"Error during transaction verification: {str(e)}")
            return False

    def _verify_basic_fields(self) -> bool:
        """Verify basic transaction fields"""
        try:
            valid = (
                isinstance(self.sender, str) and
                isinstance(self.recipient, str) and
                isinstance(self.amount, Decimal) and
                self.amount >= 0 and
                isinstance(self.timestamp, int) and
                isinstance(self.version, int) and
                self.version <= self.VERSION
            )
            
            if not valid:
                logger.warning("Basic field validation failed:")
                logger.warning(f"sender type: {type(self.sender)}")
                logger.warning(f"recipient type: {type(self.recipient)}")
                logger.warning(f"amount type: {type(self.amount)}")
                logger.warning(f"amount value: {self.amount}")
                logger.warning(f"timestamp type: {type(self.timestamp)}")
                logger.warning(f"version: {self.version}")
            
            return valid
            
        except Exception as e:
            logger.error(f"Error in basic field verification: {str(e)}")
            return False

    def _verify_size(self) -> bool:
        """Verify transaction size is within limits"""
        tx_size = len(self.to_string())
        if tx_size > self.MAX_SIZE:
            logger.warning(f"Transaction size {tx_size} exceeds limit {self.MAX_SIZE}")
            return False
        return True

    def _verify_timestamp(self) -> bool:
        """Verify transaction timestamp"""
        current_time = int(time.time())
        is_valid = (
            self.timestamp <= current_time + self.MAX_FUTURE_TIME and
            self.timestamp >= current_time - self.MAX_PAST_TIME
        )
        if not is_valid:
            logger.warning(f"Invalid timestamp: {self.timestamp}, current: {current_time}")
        return is_valid

    def _verify_transaction_data(self) -> bool:
        """Validate transaction data based on type"""
        if not self.data:
            return True
            
        try:
            if self.transaction_type == TransactionType.STAKE:
                return (
                    self.data.validator_address is not None and
                    self.data.delegation_amount is not None and
                    self.data.delegation_amount > 0
                )
            elif self.transaction_type == TransactionType.UNSTAKE:
                return (
                    self.data.validator_address is not None and
                    self.data.unbonding_time is not None
                )
            elif self.transaction_type == TransactionType.DELEGATE:
                return (
                    self.data.validator_address is not None and
                    self.data.delegation_amount is not None and
                    self.data.delegation_amount > 0
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating transaction data: {str(e)}")
            return False

    def _verify_transaction_type(self, blockchain: 'Blockchain') -> bool:
        """Verify transaction based on its type"""
        if self.transaction_type == TransactionType.TRANSFER:
            logger.debug("Transfer transaction - basic verification only")
            return True
        elif self.transaction_type == TransactionType.MINING_REWARD:
            return self._verify_mining_reward(blockchain)
        elif self.transaction_type == TransactionType.STAKE:
            return self._verify_stake(blockchain)
        elif self.transaction_type == TransactionType.UNSTAKE:
            return self._verify_unstake(blockchain)
        return False

    def _verify_mining_reward(self, blockchain: 'Blockchain') -> bool:
        """Verify mining reward transaction"""
        try:
            if self.sender != "0":
                logger.warning("Mining reward must come from system (sender='0')")
                return False
            
            current_height = len(blockchain.chain)
            expected_reward = blockchain.get_block_reward(current_height)
            
            if self.amount != expected_reward:
                logger.warning(f"Invalid reward amount. Expected: {expected_reward}, Got: {self.amount}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error in mining reward verification: {str(e)}")
            return False

    def _verify_stake(self, blockchain: 'Blockchain') -> bool:
        """Verify staking transaction"""
        try:
            if not self.data or not self.data.validator_address:
                return False
                
            if self.amount < Config.MINIMUM_STAKE:
                logger.warning(f"Stake amount {self.amount} below minimum {Config.MINIMUM_STAKE}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error in stake verification: {str(e)}")
            return False

    def _verify_unstake(self, blockchain: 'Blockchain') -> bool:
        """Verify unstaking transaction"""
        try:
            if not self.data or not self.data.validator_address:
                return False
                
            # Check if sender has sufficient stake
            current_stake = blockchain.get_validator_stake(self.sender)
            if not current_stake or current_stake < self.amount:
                logger.warning(f"Insufficient stake for unstaking: {current_stake} < {self.amount}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error in unstake verification: {str(e)}")
            return False

    def _verify_balance(self, blockchain: 'Blockchain') -> bool:
        """Verify sender has sufficient balance"""
        try:
            if self.transaction_type in [TransactionType.GENESIS, TransactionType.MINING_REWARD]:
                logger.debug("Genesis/Mining reward transaction - no balance check needed")
                return True
                
            total_amount = self.amount + self.fee
            sender_balance = blockchain.get_balance(self.sender)
            logger.debug(f"Sender balance: {sender_balance}")
            logger.debug(f"Required amount (including fee): {total_amount}")
            
            if sender_balance < total_amount:
                logger.warning(f"Insufficient balance. Has: {sender_balance}, Needs: {total_amount}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error in balance verification: {str(e)}")
            return False

    def get_status(self, blockchain: 'Blockchain') -> TransactionStatus:
        """Get current transaction status"""
        try:
            is_valid = self.verify_transaction(blockchain)
            in_mempool = self.transaction_id in {tx.transaction_id for tx in blockchain.mempool}
            confirmations = blockchain.get_transaction_confirmations(self.transaction_id)
            block_info = blockchain.get_transaction_block(self.transaction_id)
            
            return TransactionStatus(
                is_valid=is_valid,
                in_mempool=in_mempool,
                confirmations=confirmations,
                block_height=block_info['height'] if block_info else None,
                block_hash=block_info['hash'] if block_info else None
            )
        except Exception as e:
            return TransactionStatus(
                is_valid=False,
                in_mempool=False,
                confirmations=0,
                error=str(e)
            )

    def to_string(self) -> str:
        """Convert transaction to string for signing"""
        return (
            f"{self.version}{self.sender}{self.recipient}"
            f"{str(self.amount)}{self.timestamp}"
            f"{self.transaction_type.value}{self.nonce}"
            f"{self.message or ''}"
            f"{str(self.data.__dict__) if self.data else ''}"
        )

    def to_dict(self) -> Dict:
        """Convert transaction to dictionary"""
        data_dict = None
        if self.data:
            data_dict = dict(self.data.__dict__)
            if 'type' in data_dict and isinstance(data_dict['type'], TransactionType):
                data_dict['type'] = data_dict['type'].value

        return {
            "transaction_id": self.transaction_id,
            "version": self.version,
            "sender": self.sender,
            "recipient": self.recipient,
            "amount": str(self.amount),  # Convert Decimal to string
            "timestamp": self.timestamp,
            "type": self.transaction_type.value,
            "data": data_dict,
            "message": self.message,
            "signature": self.signature,
            "nonce": self.nonce,
            "fee": str(self.fee)  # Convert Decimal to string
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Transaction':
        """Create transaction from dictionary"""
        try:
            # Convert string amount to Decimal
            amount = Decimal(str(data["amount"]))
        
            # Convert transaction type to enum
            tx_type = data["type"]
            if isinstance(tx_type, str):
                tx_type = TransactionType[tx_type.upper()]
        
            tx = cls(
                sender=data["sender"],
                recipient=data["recipient"],
                amount=amount,
                transaction_type=tx_type,
                timestamp=data["timestamp"],
                message=data.get("message"),
                version=data.get("version", cls.VERSION),
                nonce=data.get("nonce", 0)
            )

            if "signature" in data:
                tx.set_signature(data["signature"])

            if "data" in data and data["data"]:
                data_copy = data["data"].copy()
            
                # Convert type if present
                if 'type' in data_copy and isinstance(data_copy['type'], str):
                    data_copy['type'] = TransactionType[data_copy['type'].upper()]
            
                # Convert numeric fields to Decimal if they exist and aren't None
                if data_copy.get('delegation_amount') is not None:
                    data_copy['delegation_amount'] = Decimal(str(data_copy['delegation_amount']))
                if data_copy.get('reward_share') is not None:
                    data_copy['reward_share'] = Decimal(str(data_copy['reward_share']))
                
                tx.data = TransactionData(**data_copy)

            return tx
        
        except Exception as e:
            logger.error(f"Error creating transaction from dict: {str(e)}")
            raise

    def __eq__(self, other: object) -> bool:
        """Compare two transactions for equality"""
        if not isinstance(other, Transaction):
            return NotImplemented
        return self.transaction_id == other.transaction_id

    def __hash__(self) -> int:
        """Hash function for transaction"""
        return hash(self.transaction_id)

    def __str__(self) -> str:
        """String representation of transaction"""
        return (
            f"Transaction(id={self.transaction_id[:8]}..., "
            f"type={self.transaction_type.value}, "
            f"sender={self.sender[:8]}..., "
            f"recipient={self.recipient[:8]}..., "
            f"amount={self.amount})"
        )

    def __repr__(self) -> str:
        """Detailed string representation of transaction"""
        return (
            f"Transaction("
            f"id='{self.transaction_id}', "
            f"version={self.version}, "
            f"type='{self.transaction_type.value}', "
            f"sender='{self.sender}', "
            f"recipient='{self.recipient}', "
            f"amount={self.amount}, "
            f"timestamp={self.timestamp}, "
            f"nonce={self.nonce})"
        )

    @classmethod
    def create_genesis(
        cls,
        recipient: str,
        amount: Union[Decimal, float],
        message: str
    ) -> 'Transaction':
        """Create a genesis transaction"""
        return cls(
            sender="0",
            recipient=recipient,
            amount=amount,
            transaction_type=TransactionType.GENESIS,
            message=message,
            timestamp=0
        )

    @classmethod
    def create_reward(
        cls,
        recipient: str,
        amount: Union[Decimal, float]
    ) -> 'Transaction':
        """Create a mining reward transaction"""
        return cls(
            sender="0",
            recipient=recipient,
            amount=amount,
            transaction_type=TransactionType.MINING_REWARD
        )

    @classmethod
    def create_stake(
        cls,
        sender: str,
        amount: Union[Decimal, float],
        validator_address: str
    ) -> 'Transaction':
        """Create a staking transaction"""
        data = {
            "validator_address": validator_address,
            "delegation_amount": Decimal(str(amount))
        }
        return cls(
            sender=sender,
            recipient=validator_address,
            amount=amount,
            transaction_type=TransactionType.STAKE,
            data=data
        )

    @classmethod
    def create_unstake(
        cls,
        sender: str,
        amount: Union[Decimal, float],
        validator_address: str
    ) -> 'Transaction':
        """Create an unstaking transaction"""
        data = {
            "validator_address": validator_address,
            "unbonding_time": int(time.time())
        }
        return cls(
            sender=sender,
            recipient=sender,  # Return stake to sender
            amount=amount,
            transaction_type=TransactionType.UNSTAKE,
            data=data
        )