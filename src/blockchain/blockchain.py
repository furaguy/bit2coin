# src/blockchain/blockchain.py
from typing import Optional, List, Dict, Set, Tuple
from decimal import Decimal
import logging
import time
import json
from dataclasses import dataclass

from .block import Block
from .transaction import Transaction, TransactionType
from .genesis_config import GenesisConfig
from ..utils.config import Config
from ..consensus.proof_of_stake import ProofOfStake

logger = logging.getLogger(__name__)

@dataclass
class BlockchainStats:
    """Statistics about the blockchain"""
    total_transactions: int
    total_blocks: int
    total_supply: Decimal
    circulating_supply: Decimal
    total_fees: Decimal
    total_staked: Decimal
    active_validators: int

class BlockchainError(Exception):
    """Base exception for blockchain-related errors"""
    pass

class Blockchain:
    def __init__(self):
        """Initialize blockchain"""
        logger.debug("Initializing blockchain")
        self.config = GenesisConfig()
        self.chain: List[Block] = []
        self.current_block_reward = self.config.initial_reward
        self.genesis_wallets = {}
        self.mempool: List[Transaction] = []
        self.utxo_set: Dict[str, List[Transaction]] = {}  # address -> list of unspent transactions
        self.validator_stakes: Dict[str, Decimal] = {}  # address -> staked amount
        self.total_staked = Decimal('0')
        self.pos_consensus = ProofOfStake()  # Change from self.pos to self.pos_consensus
        self._initialize_genesis_block()
        logger.info("Blockchain initialized successfully")

    def get_pos_consensus(self) -> ProofOfStake:
        return self.pos_consensus    

    def _initialize_genesis_block(self) -> None:
        """Initialize the blockchain with genesis block and initial wallets"""
        logger.debug("Initializing genesis block")
        try:
            # Create genesis wallets
            from ..wallet.wallet import Wallet  # Import here to avoid circular import
            unspendable_wallet = Wallet.generate_new()
            staking_wallet = Wallet.generate_new()
            
            logger.debug(f"Created genesis wallets - Unspendable: {unspendable_wallet.address}, Staking: {staking_wallet.address}")

            # Store wallet information
            self.genesis_wallets = {
                'unspendable': unspendable_wallet.address,
                'staking': staking_wallet.address
            }

            # Create genesis transactions
            genesis_transactions = [
                Transaction.create_genesis(
                    recipient=unspendable_wallet.address,
                    amount=self.config.initial_wallets['unspendable']['balance'],
                    message=self.config.initial_wallets['unspendable']['message']
                ),
                Transaction.create_genesis(
                    recipient=staking_wallet.address,
                    amount=self.config.initial_wallets['staking']['balance'],
                    message="Initial staking allocation"
                )
            ]
            
            logger.debug(f"Created genesis transactions: {[tx.to_dict() for tx in genesis_transactions]}")

            # Create genesis block
            genesis_block = Block(
                height=0,
                previous_hash="0",
                transactions=genesis_transactions,
                timestamp=0  # Unix epoch
            )
            
            logger.debug(f"Created genesis block with hash: {genesis_block.hash}")

            # Add genesis block
            self.add_block(genesis_block)
            logger.info("Genesis block initialization complete")
            
        except Exception as e:
            logger.error(f"Error initializing genesis block: {str(e)}")
            raise BlockchainError(f"Genesis block initialization failed: {str(e)}")

    def export_state(self) -> Dict:
        """Export blockchain state"""
        try:
            # Convert UTXO set to serializable format
            utxo_dict = {}
            for address, transactions in self.utxo_set.items():
                utxo_dict[address] = [tx.to_dict() for tx in transactions]

            state = {
                "chain": [block.to_dict() for block in self.chain],
                "utxo_set": utxo_dict,
                "genesis_wallets": self.genesis_wallets,
                "mempool": [tx.to_dict() for tx in self.mempool],
                "current_block_reward": str(self.current_block_reward),
                "validator_stakes": {
                    addr: str(stake) for addr, stake in self.validator_stakes.items()
                },
                "total_staked": str(self.total_staked),
                "config": {
                    "initial_reward": str(self.config.initial_reward),
                    "halving_interval": self.config.halving_interval,
                    "total_supply": str(self.config.total_supply)
                },
                "metadata": {
                    "timestamp": int(time.time()),
                    "version": "1.0.0",
                    "total_transactions": self.get_stats().total_transactions,
                    "chain_height": self.get_chain_height()
                }
            }
            logger.debug("Blockchain state exported successfully")
            return state
        except Exception as e:
            logger.error(f"Error exporting blockchain state: {str(e)}")
            raise BlockchainError(f"State export failed: {str(e)}")

    def import_state(self, state: Dict) -> None:
        """Import blockchain state"""
        try:
            logger.debug("Importing blockchain state")
            
            # Import chain
            self.chain = [Block.from_dict(block) for block in state["chain"]]
            
            # Import UTXO set
            self.utxo_set = {}
            for address, transactions in state["utxo_set"].items():
                self.utxo_set[address] = [Transaction.from_dict(tx) for tx in transactions]
            
            # Import other state
            self.genesis_wallets = state["genesis_wallets"]
            self.mempool = [Transaction.from_dict(tx) for tx in state["mempool"]]
            self.current_block_reward = Decimal(state["current_block_reward"])
            
            # Import validator stakes
            self.validator_stakes = {
                addr: Decimal(stake) for addr, stake in state.get("validator_stakes", {}).items()
            }
            self.total_staked = Decimal(state.get("total_staked", "0"))
            
            # Import config if present
            if "config" in state:
                self.config.initial_reward = Decimal(state["config"]["initial_reward"])
                self.config.halving_interval = state["config"]["halving_interval"]
                self.config.total_supply = Decimal(state["config"]["total_supply"])
                
            logger.info(f"Imported blockchain state with {len(self.chain)} blocks")
            logger.debug(f"Genesis wallets: {self.genesis_wallets}")
            
        except Exception as e:
            logger.error(f"Error importing blockchain state: {str(e)}")
            raise BlockchainError(f"State import failed: {str(e)}")

    def get_block_reward(self, block_height: int) -> Decimal:
        """Get the block reward for a given height"""
        reward = self.config.get_block_reward(block_height)
        logger.debug(f"Block reward for height {block_height}: {reward}")
        return reward

    def update_block_reward(self, height: int) -> None:
        """Update block reward based on height"""
        halvings = height // self.config.halving_interval
        if halvings > 0:
            self.current_block_reward = self.config.initial_reward / (2 ** halvings)
            logger.info(f"Block reward updated to {self.current_block_reward} at height {height}")

    def is_unspendable_address(self, address: str) -> bool:
        """Check if an address is the unspendable genesis address"""
        result = address == self.genesis_wallets.get('unspendable')
        logger.debug(f"Checking if address {address} is unspendable: {result}")
        return result

    def is_staking_address(self, address: str) -> bool:
        """Check if an address is the staking genesis address"""
        result = address == self.genesis_wallets.get('staking')
        logger.debug(f"Checking if address {address} is staking: {result}")
        return result

    def get_balance(self, address: str) -> Decimal:
        """Get balance for an address from UTXO set"""
        logger.debug(f"Getting balance for address: {address}")
        
        if address not in self.utxo_set:
            logger.debug(f"No UTXOs found for address {address}")
            return Decimal('0')
            
        balance = sum(tx.amount for tx in self.utxo_set[address])
        logger.debug(f"Balance for {address}: {balance}")
        logger.debug(f"UTXOs: {[tx.to_dict() for tx in self.utxo_set[address]]}")
        return balance

    def get_spendable_utxos(self, address: str, amount: Decimal) -> List[Transaction]:
        """Get UTXOs that sum up to at least the required amount"""
        utxos = self.utxo_set.get(address, [])
        if not utxos:
            return []
        
        total = Decimal('0')
        selected_utxos = []
        
        # Sort UTXOs by amount to minimize the number of inputs needed
        for utxo in sorted(utxos, key=lambda x: x.amount, reverse=True):
            if not utxo.is_spendable():
                continue
            selected_utxos.append(utxo)
            total += utxo.amount
            if total >= amount:
                break
                
        return selected_utxos if total >= amount else []

    def get_validator_stake(self, address: str) -> Optional[Decimal]:
        """Get validator's staked amount"""
        return self.validator_stakes.get(address)

    def update_validator_stake(self, address: str, amount: Decimal, is_addition: bool = True) -> bool:
        """Update validator stake amount"""
        try:
            current_stake = self.validator_stakes.get(address, Decimal('0'))
            
            if is_addition:
                new_stake = current_stake + amount
                self.total_staked += amount
            else:
                if current_stake < amount:
                    return False
                new_stake = current_stake - amount
                self.total_staked -= amount

            if new_stake < Config.MINIMUM_STAKE:
                if address in self.validator_stakes:
                    del self.validator_stakes[address]
            else:
                self.validator_stakes[address] = new_stake

            return True
        except Exception as e:
            logger.error(f"Error updating validator stake: {str(e)}")
            return False

    def add_transaction_to_mempool(self, transaction: Transaction) -> bool:
        """Add a new transaction to mempool if valid"""
        logger.debug(f"Attempting to add transaction to mempool: {transaction.transaction_id}")
        
        try:
            # Check mempool size limit
            if not hasattr(self, 'mempool'):
               self.mempool = []
               
            if len(self.mempool) >= Config.MAX_MEMPOOL_SIZE:
                logger.warning("Mempool is full")
                return False

            # Check if transaction already exists
            if any(tx.transaction_id == transaction.transaction_id for tx in self.mempool):
                logger.warning("Transaction already exists in mempool")
                return False

            # Check if transaction exists in blockchain
            if self.get_transaction_block(transaction.transaction_id):
                logger.warning("Transaction already exists in blockchain")
                return False

            # Validate transaction
            if not transaction.verify_transaction(self):
                logger.warning("Transaction validation failed")
                return False

            # Add to mempool
            self.mempool.append(transaction)
            logger.info(f"Transaction {transaction.transaction_id} added to mempool")
            logger.debug(f"Current mempool size: {len(self.mempool)}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding transaction to mempool: {str(e)}")
            return False

    def get_transaction_confirmations(self, tx_id: str) -> int:
        """Get number of confirmations for a transaction"""
        for block in reversed(self.chain):
            for tx in block.transactions:
                if tx.transaction_id == tx_id:
                    return len(self.chain) - block.height
        return 0

    def get_transaction_block(self, tx_id: str) -> Optional[Dict]:
        """Get block information for a transaction"""
        for block in self.chain:
            for tx in block.transactions:
                if tx.transaction_id == tx_id:
                    return {
                        "hash": block.hash,
                        "height": block.height,
                        "timestamp": block.timestamp
                    }
        return None

    def add_block(self, block: Block) -> bool:
        """Add a new block to the chain if valid"""
        logger.debug(f"Attempting to add block at height {block.height}")
        try:
            # Skip validation for genesis block
            if block.height == 0:
                # Add to chain
                self.chain.append(block)
                # Initialize UTXO set with genesis transactions
                for tx in block.transactions:
                    if tx.recipient not in self.utxo_set:
                        self.utxo_set[tx.recipient] = []
                    self.utxo_set[tx.recipient].append(tx)
                    logger.debug(f"Added genesis UTXO for {tx.recipient}: amount={tx.amount}")
                logger.info("Genesis block added successfully")
                return True

            # Basic validation for non-genesis blocks
            if not self._is_valid_block(block):
                logger.warning("Block validation failed")
                return False

            # Process stake transactions before updating UTXO set
            self._process_stake_transactions(block)

            # Update UTXO set
            self._update_utxo_set(block)
            logger.debug("UTXO set updated successfully")

            # Remove processed transactions from mempool
            self._update_mempool(block)
            logger.debug("Mempool updated successfully")

            # Update block rewards if needed
            self.update_block_reward(block.height)

            # Add block to chain
            self.chain.append(block)
            logger.info(f"Block {block.hash} added successfully at height {block.height}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding block to chain: {str(e)}")
            return False

    def _process_stake_transactions(self, block: Block) -> None:
        """Process staking-related transactions in block"""
        for tx in block.transactions:
            if tx.transaction_type == TransactionType.STAKE:
                self.update_validator_stake(tx.sender, tx.amount, True)
            elif tx.transaction_type == TransactionType.UNSTAKE:
                self.update_validator_stake(tx.sender, tx.amount, False)

    def _is_valid_block(self, block: Block) -> bool:
        """Validate a block"""
        logger.debug(f"Validating block at height {block.height}")
        
        try:
            # Check block height
            if block.height != len(self.chain):
                logger.warning(f"Invalid block height. Expected: {len(self.chain)}, Got: {block.height}")
                return False

            # Check previous hash
            if block.previous_hash != self.chain[-1].hash:
                logger.warning(f"Invalid previous hash. Expected: {self.chain[-1].hash}, Got: {block.previous_hash}")
                return False

            # Check block timestamp
            if block.timestamp > int(time.time()) + 7200:  # Not more than 2 hours in future
                logger.warning(f"Block timestamp too far in future: {block.timestamp}")
                return False

            # Check block size
            if block.size > Config.MAX_BLOCK_SIZE:
                logger.warning(f"Block size {block.size} exceeds maximum {Config.MAX_BLOCK_SIZE}")
                return False

            # Validate reward transaction if present
            if not self._validate_block_reward(block):
                logger.warning("Invalid block reward transaction")
                return False

            # Validate all transactions
            for tx in block.transactions:
                if not tx.verify_transaction(self):
                    logger.warning(f"Invalid transaction in block: {tx.transaction_id}")
                    return False

            logger.debug("Block validation successful")
            return True

        except Exception as e:
            logger.error(f"Error validating block: {str(e)}")
            return False

    def _validate_block_reward(self, block: Block) -> bool:
        """Validate block reward transaction"""
        reward_tx = None
        for tx in block.transactions:
            if tx.transaction_type == TransactionType.MINING_REWARD:
                if reward_tx:  # Only one reward transaction allowed
                    return False
                reward_tx = tx

        if not reward_tx:
            return False

        expected_reward = self.get_block_reward(block.height)
        return reward_tx.amount == expected_reward

    def _update_utxo_set(self, block: Block) -> None:
        """Update UTXO set with block transactions"""
        logger.debug(f"Updating UTXO set with block {block.hash}")
        
        for tx in block.transactions:
            # Remove spent inputs
            if tx.sender != "0":  # Not a reward/genesis transaction
                if tx.sender in self.utxo_set:
                    logger.debug(f"Processing spent UTXOs for {tx.sender}")
                    # Find and remove spent UTXO
                    spent_amount = tx.amount + tx.fee
                    remaining_utxos = []
                    for utxo in self.utxo_set[tx.sender]:
                        if spent_amount > 0:
                            spent_amount -= utxo.amount
                            logger.debug(f"Spent UTXO: {utxo.transaction_id}")
                        else:
                            remaining_utxos.append(utxo)
                    self.utxo_set[tx.sender] = remaining_utxos

            # Add new output
            if tx.recipient not in self.utxo_set:
                self.utxo_set[tx.recipient] = []
            self.utxo_set[tx.recipient].append(tx)
            logger.debug(f"Added new UTXO for {tx.recipient}: {tx.transaction_id}")

    def clean_mempool(self, max_age: int = 7200) -> None:
        """Remove expired transactions from mempool"""
        current_time = int(time.time())
        initial_size = len(self.mempool)
        self.mempool = [tx for tx in self.mempool 
                       if current_time - tx.timestamp <= max_age]
        removed = initial_size - len(self.mempool)
        if removed > 0:
            logger.info(f"Removed {removed} expired transactions from mempool")

    def _update_mempool(self, block: Block) -> None:
        """Remove processed transactions from mempool"""
        logger.debug("Updating mempool after block addition")
        initial_size = len(self.mempool)
        
        block_tx_ids = {tx.transaction_id for tx in block.transactions}
        self.mempool = [tx for tx in self.mempool if tx.transaction_id not in block_tx_ids]
        
        removed_count = initial_size - len(self.mempool)
        logger.debug(f"Removed {removed_count} transactions from mempool")
        logger.debug(f"Current mempool size: {len(self.mempool)}")

    def get_latest_blocks(self, limit: int = 10) -> List[Block]:
        """Get the latest blocks"""
        blocks = self.chain[-limit:][::-1]  # Get last 'limit' blocks in reverse order
        logger.debug(f"Retrieved {len(blocks)} latest blocks")
        return blocks

    def get_block(self, block_id: str) -> Optional[Block]:
        """Get block by height or hash"""
        logger.debug(f"Searching for block: {block_id}")
        try:
            # Try as height first
            height = int(block_id)
            if 0 <= height < len(self.chain):
                logger.debug(f"Found block by height {height}")
                return self.chain[height]
        except ValueError:
            # Try as hash
            for block in self.chain:
                if block.hash == block_id:
                    logger.debug(f"Found block by hash {block_id}")
                    return block
        
        logger.debug(f"Block not found: {block_id}")
        return None

    def get_blocks_in_range(self, start: int, end: int) -> List[Block]:
        """Get blocks within a specified height range"""
        start = max(0, start)
        end = min(end, len(self.chain) - 1)
        return self.chain[start:end + 1]

    def get_transaction(self, tx_id: str) -> Optional[Transaction]:
        """Get transaction by ID from chain or mempool"""
        # Check mempool first
        for tx in self.mempool:
            if tx.transaction_id == tx_id:
                return tx
                
        # Check blocks in chain
        for block in reversed(self.chain):  # Search from newest to oldest
            for tx in block.transactions:
                if tx.transaction_id == tx_id:
                    return tx
                    
        return None

    def get_address_transactions(self, address: str, limit: int = 100) -> List[Dict]:
        """Get transactions history for an address"""
        transactions = []
        for block in reversed(self.chain):
            for tx in block.transactions:
                if tx.sender == address or tx.recipient == address:
                    transactions.append({
                        "transaction": tx.to_dict(),
                        "block_height": block.height,
                        "confirmations": len(self.chain) - block.height,
                        "timestamp": block.timestamp
                    })
                    if len(transactions) >= limit:
                        return transactions
        return transactions

    def get_stats(self) -> BlockchainStats:
        """Get blockchain statistics"""
        total_transactions = sum(len(block.transactions) for block in self.chain)
        total_fees = sum(
            tx.fee for block in self.chain 
            for tx in block.transactions 
            if tx.transaction_type not in [TransactionType.GENESIS, TransactionType.MINING_REWARD]
        )
        
        return BlockchainStats(
            total_transactions=total_transactions,
            total_blocks=len(self.chain),
            total_supply=self.config.total_supply,
            circulating_supply=self._calculate_circulating_supply(),
            total_fees=total_fees,
            total_staked=self.total_staked,
            active_validators=len(self.validator_stakes)
        )

    def _calculate_circulating_supply(self) -> Decimal:
        """Calculate current circulating supply"""
        total_minted = sum(
            tx.amount for block in self.chain 
            for tx in block.transactions 
            if tx.transaction_type in [TransactionType.GENESIS, TransactionType.MINING_REWARD]
        )
        unspendable_balance = self.get_balance(self.genesis_wallets['unspendable'])
        return total_minted - unspendable_balance

    def get_chain_height(self) -> int:
        """Get current chain height"""
        return len(self.chain) - 1  # Height is 0-based

    def get_chain_metadata(self) -> Dict:
        """Get blockchain metadata"""
        stats = self.get_stats()
        return {
            "height": self.get_chain_height(),
            "total_transactions": stats.total_transactions,
            "total_blocks": stats.total_blocks,
            "mempool_size": len(self.mempool),
            "current_reward": str(self.current_block_reward),
            "total_staked": str(stats.total_staked),
            "active_validators": stats.active_validators,
            "circulating_supply": str(stats.circulating_supply)
        }    