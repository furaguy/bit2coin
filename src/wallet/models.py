# File: src/wallet/models.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class WalletTransaction(BaseModel):
    hash: str
    from_address: str
    to_address: str
    amount: float
    timestamp: datetime
    status: str
    type: str  # "send" or "receive"

class WalletInfo(BaseModel):
    address: str
    private_key: Optional[str]  # Only provided during creation