# src/consensus/consensus_manager.py
from typing import Optional, List, Dict
from decimal import Decimal
import time
from .proof_of_stake import ProofOfStake
from ..blockchain.block import Block
from ..blockchain.transaction import Transaction, TransactionType
from ..utils.config import Config

class ConsensusManager:
    def __init__(self, blockchain=None):  # Type hint omitted to avoid circular import
        self.blockchain = blockchain
        self.pos = ProofOfStake()
        self.current_epoch = 0
        self.epoch_start_time = int(time.time())
        
        # Block tracking
        self.last_finalized_height = 0
        self.pending_blocks: Dict[int, Block] = {}  # height -> block
        
        # Validator tracking
        self.active_validators: Dict[str, int] = {}  # validator -> last proposed block
        self.validator_votes: Dict[str, Dict[int, bool]] = {}  # validator -> (height -> vote)

    def initialize_genesis_state(self):
        """Initialize consensus state with genesis configuration"""
        # Add genesis staking wallet as first validator
        if self.blockchain and self.blockchain.genesis_wallets.get('staking'):
            self.pos.add_validator(
                self.blockchain.genesis_wallets['staking'],
                Decimal('150')
            )

    def select_validator(self, block_height: int) -> Optional[str]:
        """Select validator for new block"""
        return self.pos.select_validator(block_height)

    def validate_block(self, block: Block) -> bool:
        """Validate block and consensus rules"""
        # Special case for genesis block
        if block.height == 0:
            return self._validate_genesis_block(block)
            
        # Basic validation
        if not self._validate_basic_rules(block):
            return False
            
        # Validate block proposer
        if not self._validate_proposer(block):
            return False
            
        # Validate transactions
        if not self._validate_block_transactions(block):
            return False
            
        # Update validator statistics
        self.pos.update_validator_performance(
            block.validator,
            block.height,
            "propose",
            True
        )
            
        return True

    def _validate_genesis_block(self, block: Block) -> bool:
        """Validate genesis block"""
        if not self.blockchain:
            return False
            
        # Must have exactly 2 transactions
        if len(block.transactions) != 2:
            return False
            
        # Validate unspendable transaction
        unspendable_tx = block.transactions[0]
        if (unspendable_tx.transaction_type != TransactionType.GENESIS or
            unspendable_tx.recipient != self.blockchain.genesis_wallets['unspendable'] or
            unspendable_tx.amount != Decimal('50')):
            return False
            
        # Validate staking transaction
        staking_tx = block.transactions[1]
        if (staking_tx.transaction_type != TransactionType.GENESIS or
            staking_tx.recipient != self.blockchain.genesis_wallets['staking'] or
            staking_tx.amount != Decimal('150')):
            return False
            
        return True

    def _validate_basic_rules(self, block: Block) -> bool:
        """Validate basic consensus rules"""
        # Check block height
        if block.height != len(self.blockchain.chain):
            return False
            
        # Check previous hash
        if block.previous_hash != self.blockchain.chain[-1].hash:
            return False
            
        # Check timestamp
        if block.timestamp > int(time.time()) + 120:  # No more than 2 minutes in future
            return False
            
        return True

    def _validate_proposer(self, block: Block) -> bool:
        """Validate block proposer"""
        if not block.validator:
            return False
            
        # Check if validator is active
        if block.validator not in self.active_validators:
            return False
            
        # Check if validator was selected for this height
        selected_validator = self.select_validator(block.height)
        if selected_validator != block.validator:
            return False
            
        return True

    def _validate_block_transactions(self, block: Block) -> bool:
        """Validate block transactions"""
        # Must have reward transaction
        reward_tx = None
        for tx in block.transactions:
            if tx.transaction_type == TransactionType.MINING_REWARD:
                reward_tx = tx
                break
                
        if not reward_tx:
            return False
            
        # Validate reward amount
        expected_reward = self.blockchain.get_block_reward(block.height)
        if reward_tx.amount != expected_reward:
            return False
            
        # Validate all transactions
        for tx in block.transactions:
            if not tx.verify_transaction(self.blockchain):
                return False
                
        return True

    def process_validator_vote(
        self,
        validator: str,
        block_height: int,
        vote: bool
    ) -> bool:
        """Process validator vote for block"""
        if validator not in self.active_validators:
            return False
            
        if validator not in self.validator_votes:
            self.validator_votes[validator] = {}
            
        self.validator_votes[validator][block_height] = vote
        
        # Update validator statistics
        self.pos.update_validator_performance(
            validator,
            block_height,
            "sign",
            vote
        )
        
        # Check if block can be finalized
        self._try_finalize_block(block_height)
        
        return True

    def _try_finalize_block(self, block_height: int):
        """Try to finalize block if enough votes"""
        if block_height <= self.last_finalized_height:
            return
            
        total_stake = self.pos.get_total_stake()
        if total_stake == 0:
            return
            
        voted_stake = Decimal('0')
        for validator, votes in self.validator_votes.items():
            if block_height in votes and votes[block_height]:
                voted_stake += self.pos.get_validator_stake(validator)
                
        # Require 2/3 stake voting for finalization
        if voted_stake * 3 >= total_stake * 2:
            self._finalize_block(block_height)

    def _finalize_block(self, block_height: int):
        """Finalize block at height"""
        if block_height in self.pending_blocks:
            block = self.pending_blocks[block_height]
            # Distribute rewards
            for tx in block.transactions:
                if tx.transaction_type == TransactionType.MINING_REWARD:
                    self.pos.distribute_block_rewards(block)
                    break
            # Update finalized height
            self.last_finalized_height = block_height
            # Clean up
            del self.pending_blocks[block_height]
            # Clear old votes
            for validator in self.validator_votes:
                if block_height in self.validator_votes[validator]:
                    del self.validator_votes[validator][block_height]

    def update_epoch(self):
        """Update epoch if needed"""
        current_time = int(time.time())
        if current_time - self.epoch_start_time >= Config.EPOCH_LENGTH:
            self.current_epoch += 1
            self.epoch_start_time = current_time
            self.pos.advance_epoch()

    def get_consensus_status(self) -> Dict:
        """Get current consensus status"""
        return {
            "current_epoch": self.current_epoch,
            "last_finalized_height": self.last_finalized_height,
            "active_validators": len(self.active_validators),
            "pending_blocks": len(self.pending_blocks),
            "total_stake": str(self.pos.get_total_stake())
        }