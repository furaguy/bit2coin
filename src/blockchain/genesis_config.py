# src/blockchain/genesis_config.py

from decimal import Decimal
from typing import Dict, Any

TOTAL_SUPPLY = Decimal('21000000')
INITIAL_REWARD = Decimal('50')
HALVING_INTERVAL = 210000  # blocks (approximately 4 years with 10-minute block time)
GENESIS_MESSAGE = "bitcoin aged fine!"

class GenesisConfig:
    def __init__(self):
        self.initial_wallets: Dict[str, Any] = {
            'unspendable': {
                'balance': Decimal('50'),
                'spendable': False,
                'message': GENESIS_MESSAGE
            },
            'staking': {
                'balance': Decimal('150'),
                'spendable': True,
                'is_staking': True
            }
        }
        self.initial_reward = INITIAL_REWARD
        self.halving_interval = HALVING_INTERVAL
        self.total_supply = TOTAL_SUPPLY

    def get_block_reward(self, block_height: int) -> Decimal:
        """Calculate block reward based on height"""
        halvings = block_height // self.halving_interval
        if halvings >= 64:  # After 64 halvings, reward is 0
            return Decimal('0')
        return self.initial_reward / (2 ** halvings)