# src/blockchain/utxo.py

from dataclasses import dataclass
from typing import List, Dict, Set, Optional, Tuple, Union
import hashlib
import time
from decimal import Decimal
from enum import Enum
from ecdsa import SigningKey, VerifyingKey, SECP256k1
import base58
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TransactionPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3

@dataclass
class TransactionInput:
    """Represents a reference to an unspent transaction output"""
    txid: str  # Hash of the transaction containing the UTXO
    vout: int  # Index of the output in the transaction
    signature: Optional[bytes]  # Signature proving ownership
    public_key: bytes  # Public key of the owner

    def serialize_for_signing(self) -> bytes:
        """Serialize the input for signing, excluding the signature"""
        return f"{self.txid}{self.vout}".encode()

@dataclass
class TransactionOutput:
    """Represents an unspent transaction output"""
    amount: Decimal  # Amount of coins
    public_key_hash: str  # Hash of the recipient's public key (address)
    script: str  # Locking script (can be extended for more complex conditions)

    def serialize(self) -> bytes:
        """Serialize the output for inclusion in transaction hash"""
        return f"{float(self.amount)}{self.public_key_hash}{self.script}".encode()

class CryptoUtils:
    """Utility class for cryptographic operations"""
    
    @staticmethod
    def generate_keypair() -> Tuple[SigningKey, VerifyingKey]:
        """Generate a new keypair"""
        private_key = SigningKey.generate(curve=SECP256k1)
        public_key = private_key.get_verifying_key()
        return private_key, public_key

    @staticmethod
    def public_key_to_address(public_key: Union[VerifyingKey, bytes]) -> str:
        """Convert a public key to a blockchain address"""
        if isinstance(public_key, VerifyingKey):
            public_key = public_key.to_string()
        
        sha256_hash = hashlib.sha256(public_key).digest()
        ripemd160_hash = hashlib.new('ripemd160', sha256_hash).digest()
        
        versioned = b'\x00' + ripemd160_hash
        checksum = hashlib.sha256(hashlib.sha256(versioned).digest()).digest()[:4]
        
        binary_address = versioned + checksum
        address = base58.b58encode(binary_address).decode('ascii')
        
        return address

    @staticmethod
    def verify_address(address: str) -> bool:
        """Verify that an address is valid"""
        try:
            decoded = base58.b58decode(address)
            version = decoded[0:1]
            pub_key_hash = decoded[1:-4]
            checksum = decoded[-4:]
            
            versioned = version + pub_key_hash
            calculated_checksum = hashlib.sha256(hashlib.sha256(versioned).digest()).digest()[:4]
            
            return checksum == calculated_checksum
        except Exception:
            return False

class FeeCalculator:
    """Handles fee calculation and priority for transactions"""
    
    BASE_FEE_RATE = Decimal('0.00001')  # Satoshis per byte
    
    PRIORITY_MULTIPLIERS = {
        TransactionPriority.LOW: Decimal('1.0'),
        TransactionPriority.MEDIUM: Decimal('2.0'),
        TransactionPriority.HIGH: Decimal('3.0')
    }
    
    MIN_RELAY_FEE = Decimal('0.00001')
    MIN_MINING_FEE = Decimal('0.0001')
    
    @classmethod
    def calculate_size(cls, tx: 'Transaction') -> int:
        """Calculate the approximate size of a transaction in bytes"""
        size = 10  # Version (4) + Lock Time (4) + Input/Output count (2)
        input_size = 150  # Typical input size
        size += len(tx.inputs) * input_size
        output_size = 34  # Amount (8) + Script size (1) + Script (~25)
        size += len(tx.outputs) * output_size
        return size

    @classmethod
    def calculate_fee(cls, 
                     tx: 'Transaction', 
                     priority: TransactionPriority = TransactionPriority.MEDIUM,
                     mempool_size: int = 0) -> Decimal:
        """Calculate the recommended fee for a transaction"""
        tx_size = cls.calculate_size(tx)
        base_fee = Decimal(tx_size) * cls.BASE_FEE_RATE
        
        priority_fee = base_fee * cls.PRIORITY_MULTIPLIERS[priority]
        
        if mempool_size > 0:
            congestion_multiplier = Decimal('1.0') + (Decimal(mempool_size) / Decimal('1000000'))
            priority_fee *= congestion_multiplier
        
        final_fee = max(
            priority_fee,
            cls.MIN_RELAY_FEE if priority == TransactionPriority.LOW else cls.MIN_MINING_FEE
        )
        
        return final_fee.quantize(Decimal('0.00000001'))

class Transaction:
    """Represents a complete transaction with inputs and outputs"""
    
    def __init__(self, 
                 version: int = 1,
                 inputs: List[TransactionInput] = None,
                 outputs: List[TransactionOutput] = None,
                 locktime: int = 0,
                 priority: TransactionPriority = TransactionPriority.MEDIUM):
        self.version = version
        self.inputs = inputs or []
        self.outputs = outputs or []
        self.locktime = locktime
        self.timestamp = int(time.time())
        self.priority = priority
        self._hash = None
        self._fee = None

    def serialize_for_signing(self, input_index: int) -> bytes:
        """Serialize the transaction for signing a specific input"""
        modified_inputs = []
        for i, tx_input in enumerate(self.inputs):
            if i == input_index:
                modified_input = TransactionInput(
                    txid=tx_input.txid,
                    vout=tx_input.vout,
                    signature=None,
                    public_key=tx_input.public_key
                )
            else:
                modified_input = TransactionInput(
                    txid=tx_input.txid,
                    vout=tx_input.vout,
                    signature=None,
                    public_key=b''
                )
            modified_inputs.append(modified_input)

        data = {
            'version': self.version,
            'inputs': [{'txid': inp.txid, 'vout': inp.vout} for inp in modified_inputs],
            'outputs': [{'amount': float(out.amount), 'public_key_hash': out.public_key_hash}
                       for out in self.outputs],
            'locktime': self.locktime,
            'timestamp': self.timestamp
        }
        
        return json.dumps(data, sort_keys=True).encode()

    def sign_input(self, input_index: int, private_key: SigningKey, utxo_set: 'UTXOSet') -> bool:
        """Sign a specific input of the transaction"""
        try:
            if input_index >= len(self.inputs):
                return False
                
            tx_input = self.inputs[input_index]
            utxo = utxo_set.get_utxo(tx_input.txid, tx_input.vout)
            if not utxo:
                return False
                
            signing_data = self.serialize_for_signing(input_index)
            signature = private_key.sign(signing_data)
            
            self.inputs[input_index].signature = signature
            self.inputs[input_index].public_key = private_key.get_verifying_key().to_string()
            
            return True
        except Exception as e:
            logger.error(f"Error signing input: {str(e)}")
            return False

    @property
    def hash(self) -> str:
        """Calculate and cache the transaction hash"""
        if self._hash is None:
            serialized = self.serialize_for_signing(0)
            self._hash = hashlib.sha256(serialized).hexdigest()
        return self._hash

    @property
    def fee(self) -> Decimal:
        """Calculate the actual fee included in this transaction"""
        if self._fee is None:
            input_amount = sum(utxo.amount for utxo in self.get_input_utxos())
            output_amount = sum(output.amount for output in self.outputs)
            self._fee = input_amount - output_amount
        return self._fee

    def get_input_utxos(self) -> List[TransactionOutput]:
        """Get the UTXOs referenced by this transaction's inputs"""
        return []  # Implemented by the UTXO set

    def estimate_fee(self, mempool_size: int = 0) -> Decimal:
        """Estimate the recommended fee for this transaction"""
        return FeeCalculator.calculate_fee(self, self.priority, mempool_size)

class UTXOSet:
    """Manages the set of all unspent transaction outputs"""
    
    def __init__(self):
        self.utxos: Dict[str, Dict[int, TransactionOutput]] = {}
        self.spent_outputs: Set[tuple] = set()

    def add_transaction_outputs(self, tx: Transaction) -> None:
        """Add new transaction outputs to the UTXO set"""
        self.utxos[tx.hash] = {}
        for i, output in enumerate(tx.outputs):
            self.utxos[tx.hash][i] = output

    def spend_outputs(self, tx: Transaction) -> None:
        """Mark outputs as spent when used as inputs"""
        for tx_input in tx.inputs:
            self.spent_outputs.add((tx_input.txid, tx_input.vout))
            if tx_input.txid in self.utxos and tx_input.vout in self.utxos[tx_input.txid]:
                del self.utxos[tx_input.txid][tx_input.vout]
                if not self.utxos[tx_input.txid]:
                    del self.utxos[tx_input.txid]

    def get_utxo(self, txid: str, vout: int) -> Optional[TransactionOutput]:
        """Get an unspent transaction output if it exists"""
        return self.utxos.get(txid, {}).get(vout)

    def is_spent(self, txid: str, vout: int) -> bool:
        """Check if an output has been spent"""
        return (txid, vout) in self.spent_outputs

    def get_balance(self, public_key_hash: str) -> Decimal:
        """Calculate the balance for a given public key hash"""
        balance = Decimal('0')
        for tx_outputs in self.utxos.values():
            for output in tx_outputs.values():
                if output.public_key_hash == public_key_hash:
                    balance += output.amount
        return balance

    def validate_transaction_fee(self, tx: Transaction, mempool_size: int = 0) -> bool:
        """Validate that a transaction includes adequate fees"""
        actual_fee = tx.fee
        minimum_fee = FeeCalculator.calculate_fee(tx, tx.priority, mempool_size)
        return actual_fee >= minimum_fee and actual_fee >= FeeCalculator.MIN_RELAY_FEE

    def estimate_fee(self, tx: Transaction, priority: TransactionPriority) -> Tuple[Decimal, Decimal]:
        """Estimate fee range for a transaction"""
        min_fee = FeeCalculator.calculate_fee(tx, TransactionPriority.LOW)
        recommended_fee = FeeCalculator.calculate_fee(tx, priority)
        return min_fee, recommended_fee

class TransactionValidator:
    """Validates transactions against the UTXO set"""
    
    def __init__(self, utxo_set: UTXOSet):
        self.utxo_set = utxo_set

    def validate_transaction(self, tx: Transaction, mempool_size: int = 0) -> bool:
        """Validate a transaction"""
        try:
            if not tx.inputs or not tx.outputs:
                return False

            input_amount = Decimal('0')
            for i, tx_input in enumerate(tx.inputs):
                if self.utxo_set.is_spent(tx_input.txid, tx_input.vout):
                    return False
                    
                utxo = self.utxo_set.get_utxo(tx_input.txid, tx_input.vout)
                if not utxo:
                    return False
                    
                if not self._verify_signature(tx, i, tx_input, utxo):
                    return False
                    
                input_amount += utxo.amount

            output_amount = sum(o.amount for o in tx.outputs)

            if not self.utxo_set.validate_transaction_fee(tx, mempool_size):
                return False

            if output_amount + tx.fee > input_amount:
                return False

            return True
        except Exception as e:
            logger.error(f"Transaction validation error: {str(e)}")
            return False

    def _verify_signature(self, tx: Transaction, input_index: int,
                         tx_input: TransactionInput, utxo: TransactionOutput) -> bool:
        """Verify the signature on a transaction input"""
        try:
            signing_data = tx.serialize_for_signing(input_index)
            verifying_key = VerifyingKey.from_string(tx_input.public_key, curve=SECP256k1)
            
            if CryptoUtils.public_key_to_address(verifying_key) != utxo.public_key_hash:
                return False
            
            return verifying_key.verify(tx_input.signature, signing_data)
        except Exception as e:
            logger.error(f"Signature verification error: {str(e)}")
            return False