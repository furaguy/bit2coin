# src/wallet/wallet.py
from typing import Optional, List, Dict, Tuple
from decimal import Decimal
import time
import json
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
from ..crypto.signature import SignatureManager
from ..blockchain.transaction import Transaction, TransactionType
from ..utils.config import Config

class Wallet:
    def __init__(
        self,
        private_key: Optional[str] = None,
        blockchain = None  # Type hint omitted to avoid circular import
    ):
        """Initialize wallet with optional private key"""
        self.signature_manager = SignatureManager(private_key)
        self.address = self.signature_manager.get_address()
        self.blockchain = blockchain
        self.transactions: List[Transaction] = []
        self.nonce = 0

    def _generate_key_from_password(self, password: str, salt: Optional[bytes] = None) -> Tuple[bytes, bytes]:
        """Generate encryption key from password"""
        if salt is None:
            salt = os.urandom(16)
            
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key, salt

    @classmethod
    def generate_new(cls) -> 'Wallet':
        """Generate new wallet with random private key"""
        return cls()

    def sign_message(self, message: str) -> str:
        """Sign a message using the wallet's private key"""
        return self.signature_manager.sign_data(message)

    def verify_message(self, message: str, signature: str) -> bool:
        """Verify a message signature"""
        return self.signature_manager.verify_data(message, signature)

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
        # Verify sufficient balance if blockchain is available
        if self.blockchain and self.get_balance() < amount:
            return None
            
        transaction = Transaction(
            sender=self.address,
            recipient=recipient,
            amount=amount,
            transaction_type=transaction_type,
            data=data,
            timestamp=int(time.time())
        )
        
        # Sign transaction
        signature = self.sign_message(transaction.to_string())
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

    def unstake_tokens(self, amount: Decimal) -> Optional[Transaction]:
        """Create unstaking transaction"""
        return self.create_transaction(
            recipient=self.address,
            amount=amount,
            transaction_type=TransactionType.UNSTAKE
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
            amount=unclaimed_rewards,
            transaction_type=TransactionType.CLAIM_REWARDS
        )

    def get_transaction_history(self) -> List[Transaction]:
        """Get wallet transaction history"""
        return self.transactions.copy()

    def export_private_key(self) -> str:
        """Export private key"""
        return self.signature_manager.get_private_key_string()

    def export_public_key(self) -> str:
        """Export public key"""
        return self.signature_manager.get_public_key_string()

    def save_to_file(self, filename: str, password: str) -> bool:
        """Save wallet to encrypted file"""
        try:
            # Prepare wallet data
            wallet_data = {
                "private_key": self.export_private_key(),
                "address": self.address,
                "transactions": [tx.to_dict() for tx in self.transactions]
            }
            
            # Generate encryption key from password
            key, salt = self._generate_key_from_password(password)
            fernet = Fernet(key)
            
            # Encrypt the wallet data
            encrypted_data = fernet.encrypt(json.dumps(wallet_data).encode())
            
            # Save encrypted data with salt
            save_data = {
                "salt": base64.b64encode(salt).decode(),
                "data": base64.b64encode(encrypted_data).decode()
            }
            
            with open(filename, 'w') as f:
                json.dump(save_data, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"Error saving wallet: {str(e)}")
            return False

    @classmethod
    def load_from_file(cls, filename: str, password: str) -> Optional['Wallet']:
        """Load wallet from encrypted file"""
        try:
            # Read encrypted data
            with open(filename, 'r') as f:
                save_data = json.load(f)
            
            # Get salt and encrypted data
            salt = base64.b64decode(save_data["salt"])
            encrypted_data = base64.b64decode(save_data["data"])
            
            # Generate key from password and salt
            key, _ = cls._generate_key_from_password(password, salt)
            fernet = Fernet(key)
            
            # Decrypt data
            decrypted_data = fernet.decrypt(encrypted_data)
            wallet_data = json.loads(decrypted_data)
            
            # Create wallet instance
            wallet = cls(private_key=wallet_data["private_key"])
            
            # Restore transactions if any
            if "transactions" in wallet_data:
                for tx_data in wallet_data["transactions"]:
                    tx = Transaction.from_dict(tx_data)
                    wallet.transactions.append(tx)
            
            return wallet
            
        except Exception as e:
            print(f"Error loading wallet: {str(e)}")
            return None

    @staticmethod
    def verify_password_strength(password: str) -> Tuple[bool, str]:
        """Verify password meets minimum security requirements"""
        if len(password) < 12:
            return False, "Password must be at least 12 characters long"
            
        if not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"
            
        if not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter"
            
        if not any(c.isdigit() for c in password):
            return False, "Password must contain at least one number"
            
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password):
            return False, "Password must contain at least one special character"
            
        return True, "Password meets security requirements"

    def to_dict(self) -> Dict:
        """Convert wallet to dictionary"""
        return {
            "address": self.address,
            "balance": str(self.get_balance()),
            "transactions": len(self.transactions),
            "public_key": self.export_public_key()
        }

    def __str__(self) -> str:
        """String representation of wallet"""
        return f"Wallet(address={self.address})"