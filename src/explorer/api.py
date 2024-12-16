# File: src/explorer/api.py
from fastapi import FastAPI, HTTPException
from typing import List, Optional
from .models import Block, Transaction, Address
from .indexer import BlockchainIndexer

class ExplorerAPI:
    def __init__(self, indexer: BlockchainIndexer):
        self.indexer = indexer

    async def get_block(self, block_id: str) -> Block:
        """Get block by height or hash."""
        block = await self.indexer.db.get('blocks', block_id)
        if not block:
            raise HTTPException(status_code=404, detail="Block not found")
        return Block(**block)

    async def get_transaction(self, tx_hash: str) -> Transaction:
        """Get transaction by hash."""
        tx = await self.indexer.db.get('transactions', tx_hash)
        if not tx:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return Transaction(**tx)

    async def get_address(self, address: str) -> Address:
        """Get address details."""
        addr = await self.indexer.db.get('addresses', address)
        if not addr:
            raise HTTPException(status_code=404, detail="Address not found")
        return Address(**addr)

    async def get_latest_blocks(self, limit: int = 10) -> List[Block]:
        """Get latest blocks."""
        blocks = await self.indexer.db.get_latest('blocks', limit)
        return [Block(**block) for block in blocks]

    async def get_latest_transactions(self, limit: int = 10) -> List[Transaction]:
        """Get latest transactions."""
        txs = await self.indexer.db.get_latest('transactions', limit)
        return [Transaction(**tx) for tx in txs]
