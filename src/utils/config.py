# src/utils/config.py
from decimal import Decimal

class Config:
    # Genesis configuration
    TOTAL_SUPPLY = Decimal('21000000')
    INITIAL_BLOCK_REWARD = Decimal('50')
    HALVING_INTERVAL = 210000  # blocks (approximately 4 years)
    GENESIS_MESSAGE = "bitcoin aged fine!"
    
    # Consensus configuration
    MINIMUM_STAKE = Decimal('100')
    MAX_VALIDATORS = 100
    EPOCH_LENGTH = 2016  # blocks (approximately 2 weeks)
    
    # Network configuration
    BLOCK_TIME = 600  # 10 minutes in seconds
    MAX_BLOCK_SIZE = 1_000_000  # 1MB
    
    # Validator configuration
    VALIDATOR_COOLDOWN_PERIOD = 86400  # 24 hours in seconds
    MAX_MISSED_BLOCKS = 50
    SLASHING_LOOKBACK_PERIOD = 86400  # 24 hours
    
    # Staking configuration
    MINIMUM_DELEGATION = Decimal('10')
    UNBONDING_PERIOD = 259200  # 3 days in seconds
    REWARD_HALVING_INTERVAL = 210000  # Same as Bitcoin
    
    # Genesis validators
    GENESIS_VALIDATORS = {
        # Initial staking wallet with 150 B2C
        "GENESIS_STAKING_ADDRESS": Decimal('150')
    }