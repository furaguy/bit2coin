# src/consensus/proof_of_stake.py
from typing import Dict, List, Optional
from decimal import Decimal
import time
from .validator import Validator
from ..blockchain.block import Block
from ..blockchain.transaction import Transaction, TransactionType

class ProofOfStake:
    def __init__(self):
        # Core state
        self.validators: Dict[str, Validator] = {}
        self.total_stake: Decimal = Decimal('0')
        self.min_stake = Decimal('100')  # Minimum stake required
        
        # Mining reward configuration
        self.initial_reward = Decimal('50')  # Initial block reward
        self.halving_interval = 210000  # Blocks until halving (approximately 4 years)
        self.last_halving_height = 0
        
        # Validator tracking
        self.validator_last_block: Dict[str, int] = {}  # Last block proposed by validator
        self.active_validators: List[str] = []

    def add_validator(self, address: str, stake: Decimal) -> bool:
        """Add new validator"""
        if stake < self.min_stake:
            return False

        if address in self.validators:
            return False

        validator = Validator(
            address=address,
            stake=stake,
            start_time=int(time.time())
        )
        
        self.validators[address] = validator
        self.total_stake += stake
        self.active_validators.append(address)
        return True

    def get_block_reward(self, block_height: int) -> Decimal:
        """Calculate block reward with halving schedule"""
        halvings = block_height // self.halving_interval
        if halvings >= 64:  # After 64 halvings, reward becomes 0
            return Decimal('0')
            
        return self.initial_reward / (Decimal('2') ** halvings)

    def select_validator(self, block_height: int) -> Optional[str]:
        """Select validator for next block"""
        if not self.active_validators:
            return None

        # Simple round-robin selection for now
        # Could be enhanced with weighted random selection based on stake
        selected = self.active_validators[block_height % len(self.active_validators)]
        
        # Update last block height for validator
        self.validator_last_block[selected] = block_height
        
        return selected

    def validate_block(self, block: Block) -> bool:
        """Validate block was created by authorized validator"""
        if not block.validator or block.validator not in self.validators:
            return False

        # Verify block reward
        reward_tx = None
        for tx in block.transactions:
            if tx.transaction_type == TransactionType.MINING_REWARD:
                reward_tx = tx
                break

        if not reward_tx:
            return False

        expected_reward = self.get_block_reward(block.height)
        if reward_tx.amount != expected_reward:
            return False

        return True

    def get_validator_stake(self, address: str) -> Optional[Decimal]:
        """Get validator's current stake"""
        validator = self.validators.get(address)
        return validator.stake if validator else None

    def update_validator_stake(self, address: str, new_stake: Decimal) -> bool:
        """Update validator's stake"""
        if address not in self.validators:
            return False

        validator = self.validators[address]
        self.total_stake -= validator.stake
        validator.stake = new_stake
        self.total_stake += new_stake

        # Check if validator needs to be deactivated
        if new_stake < self.min_stake:
            self.active_validators.remove(address)
        elif address not in self.active_validators:
            self.active_validators.append(address)

        return True

    def remove_validator(self, address: str) -> bool:
        """Remove validator from active set"""
        if address not in self.validators:
            return False

        validator = self.validators[address]
        self.total_stake -= validator.stake
        del self.validators[address]
        
        if address in self.active_validators:
            self.active_validators.remove(address)
            
        return True

    def get_active_validators(self) -> List[str]:
        """Get list of active validators"""
        return self.active_validators.copy()

    def get_total_stake(self) -> Decimal:
        """Get total staked amount"""
        return self.total_stake