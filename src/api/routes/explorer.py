# File: src/api/routes/explorer.py
from fastapi import APIRouter, HTTPException
from typing import List
from src.explorer.api import ExplorerAPI
from src.explorer.models import Block, Transaction, Address

router = APIRouter(prefix="/api/v1/explorer")

@router.get("/blocks/{block_id}")
async def get_block(block_id: str):
    return await ExplorerAPI.get_block(block_id)

@router.get("/blocks/latest")
async def get_latest_blocks(limit: int = 10):
    return await ExplorerAPI.get_latest_blocks(limit)

@router.get("/transactions/{tx_hash}")
async def get_transaction(tx_hash: str):
    return await ExplorerAPI.get_transaction(tx_hash)

@router.get("/address/{address}")
async def get_address(address: str):
    return await ExplorerAPI.get_address(address)
