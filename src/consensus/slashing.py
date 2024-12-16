# File: src/consensus/slashing.py

from dataclasses import dataclass
from typing import List, Dict, Set, Optional
from enum import Enum
import time
from .validator_selection import ValidatorSelector, Stake
from .block_finalization import BlockVote

class SlashingReason(Enum):
    DOUBLE_SIGNING = "double_signing"
    INACTIVITY = "inactivity"
    INVALID_VOTE = "invalid_vote"
    MALICIOUS_FORK = "malicious_fork"

@dataclass
class SlashingEvent:
    validator: str
    reason: SlashingReason
    evidence: Dict
    timestamp: int
    penalty_amount: int

class SlashingManager:
    def __init__(
        self,
        validator_selector: ValidatorSelector,
        inactivity_threshold: int = 86400,  # 24 hours
        min_penalty_percentage: float = 0.1,  # 10% minimum slash
        max_penalty_percentage: float = 1.0   # 100% maximum slash
    ):
        self.validator_selector = validator_selector
        self.inactivity_threshold = inactivity_threshold
        self.min_penalty_percentage = min_penalty_percentage
        self.max_penalty_percentage = max_penalty_percentage
        self.slashing_history: Dict[str, List[SlashingEvent]] = {}
        self.recent_votes: Dict[str, Dict[int, BlockVote]] = {}  # validator -> height -> vote

    def check_double_signing(
        self,
        validator: str,
        block_height: int,
        vote: BlockVote
    ) -> Optional[SlashingEvent]:
        """Check if a validator has signed conflicting blocks at the same height."""
        if validator not in self.recent_votes:
            self.recent_votes[validator] = {}
            return None

        if block_height in self.recent_votes[validator]:
            previous_vote = self.recent_votes[validator][block_height]
            if previous_vote.block_hash != vote.block_hash:
                return self._create_slashing_event(
                    validator,
                    SlashingReason.DOUBLE_SIGNING,
                    {
                        "height": block_height,
                        "vote1": previous_vote,
                        "vote2": vote
                    },
                    self.max_penalty_percentage  # Double signing is a serious offense
                )
        
        # Store vote for future reference
        self.recent_votes[validator][block_height] = vote
        return None

    def check_inactivity(
        self,
        validator: str,
        current_time: Optional[int] = None
    ) -> Optional[SlashingEvent]:
        """Check if a validator has been inactive beyond the threshold."""
        stake = self.validator_selector.get_validator_stake(validator)
        if not stake or not stake.last_validation_time:
            return None

        current_time = current_time or int(time.time())
        inactive_duration = current_time - stake.last_validation_time

        if inactive_duration > self.inactivity_threshold:
            # Penalty increases with inactivity duration
            penalty_percentage = min(
                self.min_penalty_percentage * (inactive_duration / self.inactivity_threshold),
                self.max_penalty_percentage * 0.5  # Cap at 50% for inactivity
            )
            return self._create_slashing_event(
                validator,
                SlashingReason.INACTIVITY,
                {"inactive_duration": inactive_duration},
                penalty_percentage
            )
        return None

    def check_malicious_fork(
        self,
        validator: str,
        evidence: Dict
    ) -> Optional[SlashingEvent]:
        """Check if a validator has participated in a malicious fork."""
        if self._verify_fork_evidence(evidence):
            return self._create_slashing_event(
                validator,
                SlashingReason.MALICIOUS_FORK,
                evidence,
                self.max_penalty_percentage  # Malicious forking is a serious offense
            )
        return None

    def _create_slashing_event(
        self,
        validator: str,
        reason: SlashingReason,
        evidence: Dict,
        penalty_percentage: float
    ) -> SlashingEvent:
        """Create and record a slashing event."""
        stake = self.validator_selector.get_validator_stake(validator)
        if not stake:
            raise ValueError(f"No stake found for validator {validator}")

        penalty_amount = int(stake.amount * penalty_percentage)
        event = SlashingEvent(
            validator=validator,
            reason=reason,
            evidence=evidence,
            timestamp=int(time.time()),
            penalty_amount=penalty_amount
        )

        # Record the slashing event
        if validator not in self.slashing_history:
            self.slashing_history[validator] = []
        self.slashing_history[validator].append(event)

        # Apply the penalty
        self._apply_penalty(validator, penalty_amount)

        return event

    def _apply_penalty(self, validator: str, penalty_amount: int) -> None:
        """Apply the slashing penalty to a validator's stake."""
        stake = self.validator_selector.get_validator_stake(validator)
        if not stake:
            return

        new_amount = max(0, stake.amount - penalty_amount)
        if new_amount < self.validator_selector.min_stake_amount:
            # Remove validator if stake drops below minimum
            self.validator_selector.remove_stake(validator)
        else:
            # Update stake with penalty applied
            self.validator_selector.add_stake(validator, new_amount)

    def _verify_fork_evidence(self, evidence: Dict) -> bool:
        """Verify evidence of malicious fork participation."""
        # Implement detailed verification logic here
        # This should check block signatures, timestamps, and chain rules
        return True  # Placeholder

    def get_validator_history(self, validator: str) -> List[SlashingEvent]:
        """Get the slashing history for a validator."""
        return self.slashing_history.get(validator, [])

    def cleanup_old_votes(self, max_height_difference: int = 1000) -> None:
        """Clean up old votes to prevent memory bloat."""
        if not self.recent_votes:
            return

        # Find the highest block height
        max_height = max(
            max(heights.keys()) 
            for heights in self.recent_votes.values() 
            if heights
        )

        # Remove votes older than max_height_difference
        min_height = max(0, max_height - max_height_difference)
        for validator in self.recent_votes:
            self.recent_votes[validator] = {
                height: vote
                for height, vote in self.recent_votes[validator].items()
                if height >= min_height
            }