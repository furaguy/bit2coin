# src/storage/chain_reorg.py
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import logging
from ..blockchain.block import Block
from .blockchain_state import BlockchainState
from .database import DatabaseError

@dataclass
class ReorgResult:
    """Result of a chain reorganization"""
    success: bool
    old_tip: str
    new_tip: str
    common_ancestor: str
    blocks_removed: List[str]
    blocks_added: List[str]
    reorg_depth: int

class ChainReorganizer:
    """Handles blockchain reorganization and state management"""
    
    def __init__(self, state: BlockchainState, max_reorg_depth: int = 100):
        self.state = state
        self.max_reorg_depth = max_reorg_depth
        self.logger = logging.getLogger(__name__)
        
    async def handle_reorg(self, new_blocks: List[Block], current_tip: str) -> Optional[ReorgResult]:
        """
        Handle potential chain reorganization
        Returns ReorgResult if reorg occurred, None if invalid
        """
        try:
            # Find common ancestor
            fork_point, old_chain, new_chain = await self._find_fork_point(new_blocks, current_tip)
            if not fork_point:
                return None
                
            # Validate reorg depth
            reorg_depth = len(old_chain)
            if reorg_depth > self.max_reorg_depth:
                self.logger.warning(f"Reorg depth {reorg_depth} exceeds maximum {self.max_reorg_depth}")
                return None
                
            # Create state checkpoint before reorg
            checkpoint = await self._create_checkpoint()
            
            try:
                # Revert old chain
                for block in reversed(old_chain):
                    if not await self._revert_block(block):
                        raise Exception(f"Failed to revert block {block.hash}")
                
                # Apply new chain
                for block in new_chain:
                    if not await self._apply_block(block):
                        raise Exception(f"Failed to apply block {block.hash}")
                
                # Update chain head
                new_tip = new_chain[-1].hash
                if not await self._update_chain_head(new_tip):
                    raise Exception("Failed to update chain head")
                    
                return ReorgResult(
                    success=True,
                    old_tip=current_tip,
                    new_tip=new_tip,
                    common_ancestor=fork_point,
                    blocks_removed=[b.hash for b in old_chain],
                    blocks_added=[b.hash for b in new_chain],
                    reorg_depth=reorg_depth
                )
                
            except Exception as e:
                # Restore checkpoint on failure
                await self._restore_checkpoint(checkpoint)
                self.logger.error(f"Chain reorg failed: {str(e)}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error handling chain reorg: {str(e)}")
            return None
            
    async def _find_fork_point(self, new_blocks: List[Block], current_tip: str) -> Tuple[str, List[Block], List[Block]]:
        """Find the common ancestor between current chain and new chain"""
        old_chain = []
        new_chain = []
        
        # Build mapping of block height to hash for new chain
        new_blocks_by_height = {b.index: b for b in new_blocks}
        
        # Walk back current chain until we find common block
        current_block_hash = current_tip
        while current_block_hash:
            current_block_data = self.state.get_block(current_block_hash)
            if not current_block_data:
                break
                
            current_height = current_block_data["index"]
            
            # Check if this height exists in new chain
            if current_height in new_blocks_by_height:
                new_block = new_blocks_by_height[current_height]
                if new_block.hash == current_block_hash:
                    # Found common ancestor
                    return (
                        current_block_hash,
                        old_chain,
                        [b for b in new_blocks if b.index > current_height]
                    )
                    
            # Add current block to old chain
            old_chain.append(Block(**current_block_data))
            current_block_hash = current_block_data["previous_hash"]
            
        return None, [], []
        
    async def _create_checkpoint(self) -> Dict:
        """Create a state checkpoint"""
        try:
            checkpoint = {
                "metadata": self.state.get_chain_metadata(),
                "head": self.state.get_chain_head()
            }
            
            # Store checkpoint in database
            self.state.db.put("checkpoint:latest", checkpoint)
            return checkpoint
            
        except DatabaseError as e:
            self.logger.error(f"Failed to create checkpoint: {str(e)}")
            raise
            
    async def _restore_checkpoint(self, checkpoint: Dict) -> bool:
        """Restore state from checkpoint"""
        try:
            # Restore chain metadata
            metadata = checkpoint["metadata"]
            self.state.db.put("chain:metadata", metadata)
            
            # Restore chain head
            head = checkpoint["head"]
            self.state.db.put("chain:head", {"hash": head})
            
            return True
            
        except DatabaseError as e:
            self.logger.error(f"Failed to restore checkpoint: {str(e)}")
            return False
            
    async def _revert_block(self, block: Block) -> bool:
        """Revert a block's changes from state"""
        return self.state.revert_block(block)
        
    async def _apply_block(self, block: Block) -> bool:
        """Apply a block's changes to state"""
        return self.state.apply_block(block)
        
    async def _update_chain_head(self, new_tip: str) -> bool:
        """Update the chain head reference"""
        try:
            return self.state.store_chain_head(new_tip)
        except DatabaseError:
            return False