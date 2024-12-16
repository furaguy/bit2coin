# File: src/explorer/models.py
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class Block(BaseModel):
    height: int
    hash: str
    timestamp: datetime
    validator: str
    transactions: int
    size: int
    previous_hash: str

class Transaction(BaseModel):
    hash: str
    block_height: int
    from_address: str
    to_address: str
    amount: float
    timestamp: datetime
    status: str = "confirmed"

class Address(BaseModel):
    address: str
    balance: float
    total_transactions: int
    last_active: datetime