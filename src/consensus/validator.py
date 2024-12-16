# src/consensus/validator.py
from typing import Optional, Dict
from decimal import Decimal
import time
from dataclasses import dataclass
from ..utils.config import Config

@dataclass
class ValidatorStats:
    blocks_proposed: int = 0
    blocks_signed: int = 0
    blocks_missed: int = 0
    total_rewards: Decimal = Decimal('0')
    last_active: int = 0

class Validator:
    def __init__(
        self,
        address: str,
        stake: Decimal,
        start_time: Optional[int] = None
    ):
        self.address = address
        self.stake = stake
        self.start_time = start_time or int(time.time())
        self.is_active = True
        self.total_delegated = Decimal('0')
        self.cooldown_end: Optional[int] = None
        self.stats = ValidatorStats()
        
        # Delegation tracking
        self.delegators: Dict[str, Decimal] = {}  # delegator -> amount
        self.unclaimed_rewards = Decimal('0')

    def add_delegation(self, delegator: str, amount: Decimal) -> bool:
        """Add new delegation to validator"""
        if amount < Config.MINIMUM_DELEGATION:
            return False
            
        if delegator in self.delegators:
            self.delegators[delegator] += amount
        else:
            self.delegators[delegator] = amount
            
        self.total_delegated += amount
        return True

    def remove_delegation(self, delegator: str, amount: Decimal) -> bool:
        """Remove delegation from validator"""
        if delegator not in self.delegators or self.delegators[delegator] < amount:
            return False
            
        self.delegators[delegator] -= amount
        self.total_delegated -= amount
        
        if self.delegators[delegator] == 0:
            del self.delegators[delegator]
            
        return True

    def add_reward(self, amount: Decimal):
        """Add unclaimed rewards"""
        self.unclaimed_rewards += amount
        self.stats.total_rewards += amount

    def claim_rewards(self) -> Decimal:
        """Claim accumulated rewards"""
        rewards = self.unclaimed_rewards
        self.unclaimed_rewards = Decimal('0')
        return rewards

    def update_stats(self, action: str, success: bool = True):
        """Update validator statistics"""
        if action == "propose":
            if success:
                self.stats.blocks_proposed += 1
            else:
                self.stats.blocks_missed += 1
        elif action == "sign":
            if success:
                self.stats.blocks_signed += 1
                
        self.stats.last_active = int(time.time())

    def total_stake(self) -> Decimal:
        """Get total stake including delegations"""
        return self.stake + self.total_delegated

    def is_jailed(self) -> bool:
        """Check if validator is in jail (cooldown)"""
        if not self.cooldown_end:
            return False
        return int(time.time()) < self.cooldown_end

    def jail(self, duration: int):
        """Put validator in jail for specified duration"""
        self.is_active = False
        self.cooldown_end = int(time.time()) + duration

    def unjail(self) -> bool:
        """Attempt to unjail validator"""
        if not self.is_jailed() and self.stake >= Config.MINIMUM_STAKE:
            self.is_active = True
            self.cooldown_end = None
            return True
        return False

    def to_dict(self) -> Dict:
        """Convert validator to dictionary"""
        return {
            "address": self.address,
            "stake": str(self.stake),
            "start_time": self.start_time,
            "is_active": self.is_active,
            "total_delegated": str(self.total_delegated),
            "cooldown_end": self.cooldown_end,
            "stats": {
                "blocks_proposed": self.stats.blocks_proposed,
                "blocks_signed": self.stats.blocks_signed,
                "blocks_missed": self.stats.blocks_missed,
                "total_rewards": str(self.stats.total_rewards),
                "last_active": self.stats.last_active
            },
            "delegators": {
                delegator: str(amount)
                for delegator, amount in self.delegators.items()
            },
            "unclaimed_rewards": str(self.unclaimed_rewards)
        }