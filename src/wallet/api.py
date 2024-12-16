# File: src/wallet/api.py
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from typing import List
from .models import WalletTransaction, WalletInfo
from .secure_wallet import SecureWallet

class WalletAPI:
    def __init__(self, wallet: SecureWallet):
        self.wallet = wallet
        self.security = HTTPBasic()

    async def create_wallet(self, password: str) -> WalletInfo:
        """Create new wallet."""
        try:
            return self.wallet.create_wallet(password)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def load_wallet(self, credentials: HTTPBasicCredentials) -> str:
        """Load existing wallet."""
        address = self.wallet.load_wallet(credentials.password)
        if not address:
            raise HTTPException(status_code=401, detail="Invalid password")
        return address

    async def get_balance(self, credentials: HTTPBasicCredentials) -> float:
        """Get wallet balance."""
        if not self.wallet.load_wallet(credentials.password):
            raise HTTPException(status_code=401, detail="Invalid password")
        return self.wallet.get_balance()