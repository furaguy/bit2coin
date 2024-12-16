# src/storage/block_pruner.py

from typing import List, Dict, Optional
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass

from src.storage.blockchain_state import BlockchainState
from src.blockchain.block import Block
from src.exceptions import PruningError

@dataclass
class PruningConfig:
    """Configuration for block pruning"""
    # Minimum number of blocks to keep
    min_blocks_to_keep: int = 1000
    # Maximum age of blocks to keep (in days)
    max_block_age: int = 30
    # Minimum number of checkpoint blocks to keep
    min_checkpoints: int = 10
    # Maximum storage size in MB before forcing pruning
    max_storage_size_mb: int = 1000

class BlockPruner:
    """Handles pruning of old blocks while maintaining chain integrity"""
    
    def __init__(self, blockchain_state: BlockchainState, config: Optional[PruningConfig] = None):
        self.state = blockchain_state
        self.config = config or PruningConfig()
        self.logger = logging.getLogger(__name__)

    async def prune_old_blocks(self) -> bool:
        """
        Prune old blocks based on configuration settings
        Returns True if pruning was successful
        """
        try:
            current_height = self.state.get_chain_metadata()["height"]
            if current_height <= self.config.min_blocks_to_keep:
                self.logger.info("Chain too short for pruning")
                return True

            # Get pruning candidates
            candidates = await self._get_pruning_candidates()
            if not candidates:
                return True

            # Keep checkpoint blocks
            checkpoints = await self.state.checkpoint_manager.get_checkpoint_heights()
            candidates = self._filter_checkpoint_blocks(candidates, checkpoints)

            # Perform pruning
            async with self.state.db.begin(write=True) as txn:
                for block_hash in candidates:
                    await self._prune_block(txn, block_hash)

            self.logger.info(f"Successfully pruned {len(candidates)} blocks")
            return True

        except Exception as e:
            self.logger.error(f"Error during block pruning: {str(e)}")
            raise PruningError(f"Failed to prune blocks: {str(e)}")

    async def _get_pruning_candidates(self) -> List[str]:
        """Get list of block hashes that are candidates for pruning"""
        candidates = []
        current_time = datetime.now().timestamp()
        max_age = timedelta(days=self.config.max_block_age).total_seconds()

        async for key, value in self.state.db:
            if key.startswith(b"block:") and key != b"block:latest":
                block = Block.deserialize(value)
                if (current_time - block.timestamp) > max_age:
                    candidates.append(block.hash)

        return candidates

    def _filter_checkpoint_blocks(self, candidates: List[str], checkpoints: List[int]) -> List[str]:
        """Remove checkpoint blocks from pruning candidates"""
        filtered = []
        for block_hash in candidates:
            block = self.state.get_block(block_hash)
            if block.height not in checkpoints[-self.config.min_checkpoints:]:
                filtered.append(block_hash)
        return filtered

    async def _prune_block(self, txn, block_hash: str) -> None:
        """Remove a block and its associated data"""
        # Remove block data
        await txn.delete(f"block:{block_hash}".encode())
        
        # Remove associated transaction data
        block = self.state.get_block(block_hash)
        for tx in block.transactions:
            await txn.delete(f"tx:{tx.hash}".encode())

    async def check_storage_size(self) -> bool:
        """Check if storage size exceeds configured maximum"""
        db_size = await self.state.get_database_size()
        return db_size > (self.config.max_storage_size_mb * 1024 * 1024)

    async def auto_prune(self) -> bool:
        """
        Automatically prune blocks if necessary based on storage size
        Returns True if pruning was performed
        """
        if await self.check_storage_size():
            self.logger.info("Storage size exceeded, initiating auto-pruning")
            return await self.prune_old_blocks()
        return False