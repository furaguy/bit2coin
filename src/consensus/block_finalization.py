# File: src/consensus/block_finalization.py

from dataclasses import dataclass
from typing import List, Dict, Optional, Set
import time
from hashlib import sha256
from .validator_selection import ValidatorSelector

@dataclass
class BlockVote:
    validator: str
    block_hash: str
    timestamp: int
    signature: str

class BlockFinalizer:
    def __init__(
        self,
        validator_selector: ValidatorSelector,
        finality_threshold: float = 0.67,  # 67% of validators must vote
        vote_timeout: int = 300  # 5 minutes in seconds
    ):
        self.validator_selector = validator_selector
        self.finality_threshold = finality_threshold
        self.vote_timeout = vote_timeout
        self.pending_blocks: Dict[str, Set[BlockVote]] = {}  # block_hash -> votes
        self.finalized_blocks: Set[str] = set()
        self.latest_finalized_height = 0

    def submit_vote(
        self,
        validator: str,
        block_hash: str,
        block_height: int,
        signature: str
    ) -> bool:
        """Submit a vote for a block from a validator."""
        # Verify validator is eligible
        if not self.validator_selector.is_active_validator(validator):
            return False

        # Check if block is already finalized
        if block_hash in self.finalized_blocks:
            return False

        # Create new vote
        vote = BlockVote(
            validator=validator,
            block_hash=block_hash,
            timestamp=int(time.time()),
            signature=signature
        )

        # Initialize vote set for this block if needed
        if block_hash not in self.pending_blocks:
            self.pending_blocks[block_hash] = set()

        # Add vote (Set ensures no duplicate votes from same validator)
        self.pending_blocks[block_hash].add(vote)

        # Check if block can be finalized
        if self._check_finalization(block_hash, block_height):
            self._finalize_block(block_hash, block_height)
            return True

        return True

    def _check_finalization(self, block_hash: str, block_height: int) -> bool:
        """Check if a block has enough votes to be finalized."""
        if block_hash not in self.pending_blocks:
            return False

        current_time = int(time.time())
        valid_votes = set()
        
        # Get total active stake for threshold calculation
        total_stake = self.validator_selector.get_total_staked()
        if total_stake == 0:
            return False

        # Filter valid votes and calculate total stake
        stake_voted = 0
        for vote in self.pending_blocks[block_hash]:
            # Skip expired votes
            if current_time - vote.timestamp > self.vote_timeout:
                continue

            # Get validator's stake
            stake = self.validator_selector.get_validator_stake(vote.validator)
            if not stake:
                continue

            valid_votes.add(vote)
            stake_voted += stake.amount

        # Check if we have enough stake voting for finalization
        stake_threshold = total_stake * self.finality_threshold
        return stake_voted >= stake_threshold

    def _finalize_block(self, block_hash: str, block_height: int) -> None:
        """Mark a block as finalized and clean up."""
        self.finalized_blocks.add(block_hash)
        self.latest_finalized_height = max(
            self.latest_finalized_height,
            block_height
        )

        # Clean up pending votes for this block
        del self.pending_blocks[block_hash]

        # Clean up old pending blocks
        self._cleanup_old_votes()

    def _cleanup_old_votes(self) -> None:
        """Remove expired votes and blocks that can't be finalized."""
        current_time = int(time.time())
        blocks_to_remove = set()

        for block_hash, votes in self.pending_blocks.items():
            # Remove expired votes
            expired_votes = {
                vote for vote in votes
                if current_time - vote.timestamp > self.vote_timeout
            }
            votes.difference_update(expired_votes)

            # If no valid votes remain, mark block for removal
            if not votes:
                blocks_to_remove.add(block_hash)

        # Remove blocks with no valid votes
        for block_hash in blocks_to_remove:
            del self.pending_blocks[block_hash]

    def get_finalization_status(self, block_hash: str) -> Dict:
        """Get the current finalization status of a block."""
        if block_hash in self.finalized_blocks:
            return {
                "status": "finalized",
                "votes": 0,
                "required_votes": 0
            }

        if block_hash not in self.pending_blocks:
            return {
                "status": "unknown",
                "votes": 0,
                "required_votes": 0
            }

        total_stake = self.validator_selector.get_total_staked()
        required_stake = total_stake * self.finality_threshold
        current_stake = sum(
            self.validator_selector.get_validator_stake(vote.validator).amount
            for vote in self.pending_blocks[block_hash]
            if self.validator_selector.get_validator_stake(vote.validator)
        )

        return {
            "status": "pending",
            "stake_voted": current_stake,
            "required_stake": required_stake,
            "completion_percentage": (current_stake / required_stake * 100) 
                if required_stake > 0 else 0
        }