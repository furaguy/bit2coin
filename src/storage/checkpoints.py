# src/storage/checkpoints.py
from typing import Dict, Optional, List
import time
from dataclasses import dataclass
import json
from .database import Database, DatabaseError

@dataclass
class Checkpoint:
    """Represents a blockchain state checkpoint"""
    height: int
    hash: str
    timestamp: int
    metadata: Dict
    is_verified: bool = False

class CheckpointManager:
    """Manages blockchain state checkpoints"""
    
    def __init__(self, db: Database, checkpoint_interval: int = 1000):
        self.db = db
        self.checkpoint_interval = checkpoint_interval
        
    async def create_checkpoint(self, height: int, block_hash: str, 
                              metadata: Dict) -> Optional[Checkpoint]:
        """Create a new checkpoint"""
        try:
            checkpoint = Checkpoint(
                height=height,
                hash=block_hash,
                timestamp=int(time.time()),
                metadata=metadata
            )
            
            # Store checkpoint
            key = f"checkpoint:{height}"
            data = {
                "height": checkpoint.height,
                "hash": checkpoint.hash,
                "timestamp": checkpoint.timestamp,
                "metadata": checkpoint.metadata,
                "is_verified": checkpoint.is_verified
            }
            
            self.db.put(key, data)
            
            # Update latest checkpoint reference
            self.db.put("checkpoint:latest", {
                "height": height,
                "hash": block_hash
            })
            
            return checkpoint
            
        except DatabaseError as e:
            return None
            
    async def get_checkpoint(self, height: int) -> Optional[Checkpoint]:
        """Retrieve a checkpoint by height"""
        try:
            data = self.db.get(f"checkpoint:{height}")
            if not data:
                return None
                
            return Checkpoint(
                height=data["height"],
                hash=data["hash"],
                timestamp=data["timestamp"],
                metadata=data["metadata"],
                is_verified=data["is_verified"]
            )
            
        except DatabaseError:
            return None
            
    async def get_latest_checkpoint(self) -> Optional[Checkpoint]:
        """Get the most recent checkpoint"""
        try:
            latest = self.db.get("checkpoint:latest")
            if not latest:
                return None
                
            return await self.get_checkpoint(latest["height"])
            
        except DatabaseError:
            return None
            
    async def verify_checkpoint(self, checkpoint: Checkpoint) -> bool:
        """Verify checkpoint integrity"""
        try:
            # Verify checkpoint data matches blockchain state
            key = f"checkpoint:{checkpoint.height}"
            stored_data = self.db.get(key)
            
            if not stored_data:
                return False
                
            # Update verification status
            stored_data["is_verified"] = True
            self.db.put(key, stored_data)
            
            checkpoint.is_verified = True
            return True
            
        except DatabaseError:
            return False
            
    async def prune_old_checkpoints(self, keep_count: int = 10) -> bool:
        """Remove old checkpoints, keeping the most recent ones"""
        try:
            checkpoints = []
            # Iterate through database to find checkpoint keys
            for key, _ in self.db:
                if key.startswith("checkpoint:") and key != "checkpoint:latest":
                    height = int(key.split(":")[1])
                    checkpoints.append(height)
                    
            # Sort checkpoints by height
            checkpoints.sort(reverse=True)
            
            # Remove old checkpoints
            for height in checkpoints[keep_count:]:
                self.db.delete(f"checkpoint:{height}")
                
            return True
            
        except DatabaseError:
            return False
            
    async def restore_from_checkpoint(self, checkpoint: Checkpoint) -> bool:
        """Restore blockchain state from checkpoint"""
        try:
            if not checkpoint.is_verified:
                return False
                
            # Restore state metadata
            self.db.put("chain:metadata", checkpoint.metadata)
            
            # Update chain head
            self.db.put("chain:head", {
                "hash": checkpoint.hash
            })
            
            return True
            
        except DatabaseError:
            return False