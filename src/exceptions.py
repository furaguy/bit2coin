# src/exceptions.py

class BlockchainError(Exception):
    """Base exception class for blockchain-related errors"""
    pass

class StorageError(BlockchainError):
    """Base exception class for storage-related errors"""
    pass

class DatabaseError(StorageError):
    """Raised when database operations fail"""
    pass

class ReorgError(StorageError):
    """Raised when chain reorganization fails"""
    pass

class CheckpointError(StorageError):
    """Raised when checkpoint operations fail"""
    pass

class PruningError(StorageError):
    """Raised when block pruning operations fail"""
    pass

class ValidationError(BlockchainError):
    """Raised when validation fails"""
    pass

class ConsensusError(BlockchainError):
    """Raised when consensus rules are violated"""
    pass

class NetworkError(BlockchainError):
    """Raised when network operations fail"""
    pass

class WalletError(BlockchainError):
    """Raised when wallet operations fail"""
    pass

class TransactionError(BlockchainError):
    """Raised when transaction operations fail"""
    pass

class MemPoolError(BlockchainError):
    """Raised when mempool operations fail"""
    pass