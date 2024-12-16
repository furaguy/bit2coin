# File: src/api/routes/wallet.py
from fastapi import APIRouter, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from src.wallet.api import WalletAPI
from src.wallet.models import WalletTransaction, WalletInfo

router = APIRouter(prefix="/api/v1/wallet")

@router.post("/create")
async def create_wallet(password: str):
    return await WalletAPI.create_wallet(password)

@router.get("/balance")
async def get_balance(credentials: HTTPBasicCredentials = Depends(HTTPBasic())):
    return await WalletAPI.get_balance(credentials)