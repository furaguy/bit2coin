# File: src/wallet/secure_wallet.py
from typing import Optional, Dict, List
from datetime import datetime
import os
import json
from cryptography.fernet import Fernet
from eth_account import Account
import web3
from .models import WalletTransaction, WalletInfo

class SecureWallet:
    def __init__(self, storage_path: str = "wallet_data"):
        self.storage_path = storage_path
        self.encryption_key = self._load_or_create_key()
        self.fernet = Fernet(self.encryption_key)
        os.makedirs(storage_path, exist_ok=True)

    def _load_or_create_key(self) -> bytes:
        key_path = os.path.join(self.storage_path, "wallet.key")
        if os.path.exists(key_path):
            with open(key_path, "rb") as f:
                return f.read()
        key = Fernet.generate_key()
        with open(key_path, "wb") as f:
            f.write(key)
        return key

    def create_wallet(self, password: str) -> WalletInfo:
        """Create new wallet with encrypted private key."""
        account = Account.create()
        encrypted_key = self._encrypt_private_key(account.key.hex(), password)
        
        wallet_data = {
            "address": account.address,
            "encrypted_private_key": encrypted_key.decode()
        }
        
        with open(os.path.join(self.storage_path, "wallet.json"), "w") as f:
            json.dump(wallet_data, f)
        
        return WalletInfo(
            address=account.address,
            private_key=account.key.hex()  # Only shown once
        )

    def load_wallet(self, password: str) -> Optional[str]:
        """Load wallet with password."""
        try:
            with open(os.path.join(self.storage_path, "wallet.json"), "r") as f:
                wallet_data = json.load(f)
            self._decrypt_private_key(wallet_data["encrypted_private_key"], password)
            return wallet_data["address"]
        except Exception:
            return None

    def _encrypt_private_key(self, private_key: str, password: str) -> bytes:
        return self.fernet.encrypt(private_key.encode())

    def _decrypt_private_key(self, encrypted_key: str, password: str) -> str:
        return self.fernet.decrypt(encrypted_key.encode()).decode()