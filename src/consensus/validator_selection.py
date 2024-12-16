# File: src/consensus/validator_selection.py

from dataclasses import dataclass
from typing import List, Dict, Optional
import time
import random
from hashlib import sha256

@dataclass
class Stake:
    address: str
    amount: int
    timestamp: int
    last_validation_time: Optional[int] = None

class ValidatorSelector:
    def __init__(self, min_stake_amount: int = 1000, lockup_period: int = 86400):
        self.stakes: Dict[str, Stake] = {}
        self.min_stake_amount = min_stake_amount  # Minimum stake required to be validator
        self.lockup_period = lockup_period  # 24 hours in seconds
        self.total_staked = 0

    def add_stake(self, address: str, amount: int) -> bool:
        """Add or update stake for an address."""
        if amount < self.min_stake_amount:
            return False

        if address in self.stakes:
            self.total_staked -= self.stakes[address].amount
        
        self.stakes[address] = Stake(
            address=address,
            amount=amount,
            timestamp=int(time.time())
        )
        self.total_staked += amount
        return True

    def remove_stake(self, address: str) -> bool:
        """Remove stake for an address after lockup period."""
        if address not in self.stakes:
            return False

        stake = self.stakes[address]
        current_time = int(time.time())
        
        if current_time - stake.timestamp < self.lockup_period:
            return False

        self.total_staked -= stake.amount
        del self.stakes[address]
        return True

    def select_validator(self, block_height: int, previous_block_hash: str) -> Optional[str]:
        """Select a validator for the next block using weighted random selection."""
        if not self.stakes:
            return None

        # Create seed from block height and previous hash for deterministic selection
        seed = f"{block_height}{previous_block_hash}"
        seed_hash = int(sha256(seed.encode()).hexdigest(), 16)
        random.seed(seed_hash)

        # Weight selection by stake amount
        selection_pool = []
        for address, stake in self.stakes.items():
            # Skip if validator was recently selected
            if (stake.last_validation_time and 
                time.time() - stake.last_validation_time < 300):  # 5-minute cooldown
                continue
                
            # Add weighted entries based on stake amount
            weight = stake.amount / self.min_stake_amount
            selection_pool.extend([address] * int(weight))

        if not selection_pool:
            return None

        # Select validator
        selected_validator = random.choice(selection_pool)
        
        # Update last validation time
        self.stakes[selected_validator].last_validation_time = int(time.time())
        
        return selected_validator

    def get_validator_stake(self, address: str) -> Optional[Stake]:
        """Get stake information for a validator."""
        return self.stakes.get(address)

    def is_active_validator(self, address: str) -> bool:
        """Check if an address is an active validator."""
        return (address in self.stakes and 
                self.stakes[address].amount >= self.min_stake_amount)

    def get_total_staked(self) -> int:
        """Get total amount staked in the network."""
        return self.total_staked

    def get_active_validators(self) -> List[str]:
        """Get list of all active validator addresses."""
        return [addr for addr in self.stakes.keys() 
                if self.stakes[addr].amount >= self.min_stake_amount]