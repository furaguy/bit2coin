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
    MAX_MEMPOOL_SIZE = 10000  # Maximum number of transactions in mempool
    MAX_TRANSACTION_SIZE = 100_000  # 100KB per transaction

    # Validator configuration
    VALIDATOR_COOLDOWN_PERIOD = 86400  # 24 hours in seconds
    MAX_MISSED_BLOCKS = 50
    SLASHING_LOOKBACK_PERIOD = 86400  # 24 hours
    VALIDATOR_MINIMUM_BLOCK_TIME = 10  # Minimum seconds between blocks
    MAX_VALIDATOR_CANDIDATES = 100

    # Staking configuration
    MINIMUM_DELEGATION = Decimal('10')
    UNBONDING_PERIOD = 259200  # 3 days in seconds
    REWARD_HALVING_INTERVAL = 210000  # Same as Bitcoin
    MINIMUM_COMMISSION_RATE = Decimal('0.01')  # 1%
    MAXIMUM_COMMISSION_RATE = Decimal('0.20')  # 20%

    # Transaction configuration
    MINIMUM_TRANSACTION_FEE = Decimal('0.0001')
    MINIMUM_RELAY_FEE = Decimal('0.00001')
    MAX_TRANSACTIONS_PER_BLOCK = 2000
    MAX_BLOCK_WEIGHT = 4_000_000  # Similar to Bitcoin's weight limit

    # Peer configuration
    MAX_PEERS = 125
    MIN_PEERS = 8
    PEER_DISCOVERY_INTERVAL = 300  # 5 minutes
    MAX_PEER_AGE = 3600  # 1 hour
    BAN_THRESHOLD = 100
    BAN_DURATION = 86400  # 24 hours

    # Genesis validators
    GENESIS_VALIDATORS = {
        # Initial staking wallet with 150 B2C
        "GENESIS_STAKING_ADDRESS": Decimal('150')
    }

    # Network magic numbers
    MAINNET_MAGIC = 0xD9B4BEF9
    TESTNET_MAGIC = 0x0709110B
    CURRENT_NETWORK_MAGIC = TESTNET_MAGIC

    # Protocol versioning
    PROTOCOL_VERSION = 1
    MIN_PEER_PROTOCOL_VERSION = 1
    MAX_PEER_PROTOCOL_VERSION = 1

    # Database configuration
    MAX_DATABASE_SIZE = 1024 * 1024 * 1024 * 100  # 100 GB
    MAX_OPEN_FILES = 1000
    DB_CACHE_SIZE = 1024 * 1024 * 32  # 32 MB cache

    # Chain reorganization limits
    MAX_REORG_DEPTH = 100
    MAX_FUTURE_BLOCK_TIME = 7200  # 2 hours
    MINIMUM_CHAIN_WORK = 4000  # Minimum number of blocks