# src/blockchain/blockchain.py
from typing import Optional, List, Dict
from decimal import Decimal
from .genesis_config import GenesisConfig
from .block import Block
from .transaction import Transaction
from ..wallet.wallet import Wallet
import time

class Blockchain:
    def __init__(self):
        self.config = GenesisConfig()
        self.chain: List[Block] = []
        self.current_block_reward = self.config.initial_reward
        self.genesis_wallets = {}
        self.mempool: List[Transaction] = []
        self.utxo_set: Dict[str, List[Transaction]] = {}  # address -> list of unspent transactions
        self._initialize_genesis_block()

    def _initialize_genesis_block(self) -> None:
        """Initialize the blockchain with genesis block and initial wallets"""
        # Create genesis wallets
        unspendable_wallet = Wallet.generate_new()
        staking_wallet = Wallet.generate_new()

        # Store wallet information
        self.genesis_wallets = {
            'unspendable': unspendable_wallet.address,
            'staking': staking_wallet.address
        }

        # Create genesis transactions
        genesis_transactions = [
            Transaction(
                sender="0",  # System
                recipient=unspendable_wallet.address,
                amount=self.config.initial_wallets['unspendable']['balance'],
                message=self.config.initial_wallets['unspendable']['message']
            ),
            Transaction(
                sender="0",  # System
                recipient=staking_wallet.address,
                amount=self.config.initial_wallets['staking']['balance']
            )
        ]

        # Create genesis block
        genesis_block = Block(
            height=0,
            previous_hash="0",
            transactions=genesis_transactions,
            timestamp=0  # Unix epoch
        )

        # Initialize UTXO set with genesis transactions
        for tx in genesis_transactions:
            if tx.recipient not in self.utxo_set:
                self.utxo_set[tx.recipient] = []
            self.utxo_set[tx.recipient].append(tx)

        self.chain.append(genesis_block)

    def get_block_reward(self, height: int) -> Decimal:
        """Get the block reward for a given height"""
        return self.config.get_block_reward(height)

    def is_unspendable_address(self, address: str) -> bool:
        """Check if an address is the unspendable genesis address"""
        return address == self.genesis_wallets.get('unspendable')

    def is_staking_address(self, address: str) -> bool:
        """Check if an address is the staking genesis address"""
        return address == self.genesis_wallets.get('staking')

    def get_balance(self, address: str) -> Decimal:
        """Get balance for an address from UTXO set"""
        if address not in self.utxo_set:
            return Decimal('0')
        return sum(tx.amount for tx in self.utxo_set[address])

    def add_transaction_to_mempool(self, transaction: Transaction) -> bool:
        """Add a new transaction to mempool if valid"""
        if not transaction.is_valid(self):
            return False
        self.mempool.append(transaction)
        return True

    def create_new_block(self, validator_address: str) -> Block:
        """Create a new block with pending transactions"""
        previous_block = self.chain[-1]
        height = len(self.chain)
        
        # Start with the block reward transaction
        reward = self.get_block_reward(height)
        reward_tx = Transaction(
            sender="0",  # System
            recipient=validator_address,
            amount=reward
        )
        
        # Get transactions from mempool
        block_transactions = [reward_tx] + self.mempool[:99]  # Limit to 100 transactions including reward
        
        # Create new block
        new_block = Block(
            height=height,
            previous_hash=previous_block.hash,
            transactions=block_transactions,
            timestamp=int(time.time())
        )

        return new_block

    def add_block(self, block: Block) -> bool:
        """Add a new block to the chain if valid"""
        # Basic validation
        if not self._is_valid_block(block):
            return False

        # Update UTXO set
        self._update_utxo_set(block)

        # Remove processed transactions from mempool
        self._update_mempool(block)

        # Add block to chain
        self.chain.append(block)
        return True

    def _is_valid_block(self, block: Block) -> bool:
        """Validate a block"""
        # Check block height
        if block.height != len(self.chain):
            return False

        # Check previous hash
        if block.previous_hash != self.chain[-1].hash:
            return False

        # Validate all transactions
        for tx in block.transactions:
            if not tx.is_valid(self):
                return False

        return True

    def _update_utxo_set(self, block: Block) -> None:
        """Update UTXO set with block transactions"""
        for tx in block.transactions:
            # Remove spent inputs
            if tx.sender != "0":  # Not a reward transaction
                if tx.sender in self.utxo_set:
                    # Find and remove spent UTXO
                    spent_amount = tx.amount
                    remaining_utxos = []
                    for utxo in self.utxo_set[tx.sender]:
                        if spent_amount > 0:
                            spent_amount -= utxo.amount
                        else:
                            remaining_utxos.append(utxo)
                    self.utxo_set[tx.sender] = remaining_utxos

            # Add new output
            if tx.recipient not in self.utxo_set:
                self.utxo_set[tx.recipient] = []
            self.utxo_set[tx.recipient].append(tx)

    def _update_mempool(self, block: Block) -> None:
        """Remove processed transactions from mempool"""
        block_tx_hashes = {tx.hash for tx in block.transactions}
        self.mempool = [tx for tx in self.mempool if tx.hash not in block_tx_hashes]

    def get_latest_blocks(self, limit: int = 10) -> List[Block]:
        """Get the latest blocks"""
        return self.chain[-limit:][::-1]

    def get_block(self, block_id: str) -> Optional[Block]:
        """Get block by height or hash"""
        try:
            # Try as height first
            height = int(block_id)
            if 0 <= height < len(self.chain):
                return self.chain[height]
        except ValueError:
            # Try as hash
            for block in self.chain:
                if block.hash == block_id:
                    return block
        return None