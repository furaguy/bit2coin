# File: src/explorer/indexer.py
from typing import Dict, List, Optional
from datetime import datetime
from .models import Block, Transaction, Address
from src.blockchain.blockchain import Blockchain
from src.storage.database import Database

class BlockchainIndexer:
    def __init__(self, blockchain: Blockchain, db: Database):
        self.blockchain = blockchain
        self.db = db
        self.last_indexed_height = 0

    async def index_blocks(self, start_height: int = 0) -> None:
        """Index blockchain data from given height."""
        current_height = self.blockchain.get_height()
        
        for height in range(start_height, current_height + 1):
            block = await self.blockchain.get_block(height)
            if block:
                await self._index_block(block)
                self.last_indexed_height = height

    async def _index_block(self, block: Block) -> None:
        """Index a single block and its transactions."""
        # Index block data
        block_data = {
            'height': block.height,
            'hash': block.hash,
            'timestamp': block.timestamp,
            'validator': block.validator,
            'transactions': len(block.transactions),
            'size': len(str(block))
        }
        await self.db.insert('blocks', block_data)

        # Index transactions
        for tx in block.transactions:
            await self._index_transaction(tx, block.height)

    async def _index_transaction(self, tx: Transaction, block_height: int) -> None:
        """Index a single transaction."""
        tx_data = {
            'hash': tx.hash,
            'block_height': block_height,
            'from_address': tx.from_address,
            'to_address': tx.to_address,
            'amount': tx.amount,
            'timestamp': tx.timestamp
        }
        await self.db.insert('transactions', tx_data)

        # Update address balances
        await self._update_address(tx.from_address, -tx.amount)
        await self._update_address(tx.to_address, tx.amount)

    async def _update_address(self, address: str, amount_change: float) -> None:
        """Update address balance and transaction count."""
        address_data = await self.db.get('addresses', address)
        if not address_data:
            address_data = {
                'address': address,
                'balance': 0,
                'total_transactions': 0,
                'last_active': datetime.now()
            }
        
        address_data['balance'] += amount_change
        address_data['total_transactions'] += 1
        address_data['last_active'] = datetime.now()
        
        await self.db.insert('addresses', address_data)
