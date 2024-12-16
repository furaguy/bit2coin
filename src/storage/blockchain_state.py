# src/storage/blockchain_state.py
from typing import Dict, Set, Optional, List
from decimal import Decimal
from ..blockchain.transaction import Transaction
from ..utils.config import Config

class BlockchainState:
    def __init__(self):
        # Core state tracking
        self.balances: Dict[str, Decimal] = {}
        self.unspendable_utxos: Set[str] = set()  # Transaction IDs
        self.staking_utxos: Set[str] = set()  # Transaction IDs
        
        # UTXO tracking
        self.utxo_set: Dict[str, List[Transaction]] = {}  # address -> list of unspent transactions
        
        # Genesis state
        self.genesis_addresses: Dict[str, str] = {}  # type -> address
        
        # Staking state
        self.validator_stakes: Dict[str, Decimal] = {}  # validator -> stake amount
        self.total_staked: Decimal = Decimal('0')

    def initialize_genesis_state(self, unspendable_address: str, staking_address: str):
        """Initialize genesis state"""
        self.genesis_addresses = {
            'unspendable': unspendable_address,
            'staking': staking_address
        }
        
        # Set initial balances
        self.balances[unspendable_address] = Decimal('50')  # Unspendable genesis coins
        self.balances[staking_address] = Decimal('150')  # Initial staking balance
        
        # Initialize validator stake
        self.validator_stakes[staking_address] = Decimal('150')
        self.total_staked = Decimal('150')

    def update_balance(self, address: str, amount: Decimal) -> bool:
        """Update address balance"""
        if address not in self.balances:
            self.balances[address] = Decimal('0')
        
        new_balance = self.balances[address] + amount
        if new_balance < 0:
            return False
            
        self.balances[address] = new_balance
        return True

    def process_transaction(self, transaction: Transaction) -> bool:
        """Process transaction and update state"""
        # Handle genesis transactions
        if transaction.transaction_type == "genesis":
            if transaction.recipient == self.genesis_addresses['unspendable']:
                self.unspendable_utxos.add(transaction.transaction_id)
            return True
            
        # Cannot spend from unspendable address
        if transaction.sender == self.genesis_addresses['unspendable']:
            return False
            
        # Update balances
        if not self.update_balance(transaction.sender, -transaction.amount):
            return False
        self.update_balance(transaction.recipient, transaction.amount)
        
        # Update UTXO set
        if transaction.sender in self.utxo_set:
            # Remove spent UTXOs
            self.utxo_set[transaction.sender] = [
                utxo for utxo in self.utxo_set[transaction.sender]
                if utxo.transaction_id != transaction.transaction_id
            ]
            
        if transaction.recipient not in self.utxo_set:
            self.utxo_set[transaction.recipient] = []
        self.utxo_set[transaction.recipient].append(transaction)
        
        return True

    def get_balance(self, address: str) -> Decimal:
        """Get address balance"""
        return self.balances.get(address, Decimal('0'))

    def get_utxos(self, address: str) -> List[Transaction]:
        """Get unspent transactions for address"""
        return self.utxo_set.get(address, [])

    def is_unspendable(self, address: str) -> bool:
        """Check if address is unspendable genesis address"""
        return address == self.genesis_addresses.get('unspendable')

    def is_staking_address(self, address: str) -> bool:
        """Check if address is genesis staking address"""
        return address == self.genesis_addresses.get('staking')

    def update_stake(self, validator: str, amount: Decimal) -> bool:
        """Update validator stake"""
        if validator not in self.validator_stakes:
            if amount < Config.MINIMUM_STAKE:
                return False
            self.validator_stakes[validator] = amount
        else:
            new_stake = self.validator_stakes[validator] + amount
            if new_stake < 0:
                return False
            if new_stake < Config.MINIMUM_STAKE:
                del self.validator_stakes[validator]
            else:
                self.validator_stakes[validator] = new_stake
                
        self.total_staked = sum(self.validator_stakes.values())
        return True

    def export_state(self) -> Dict:
        """Export current state"""
        return {
            "balances": {
                addr: str(balance)
                for addr, balance in self.balances.items()
            },
            "genesis_addresses": self.genesis_addresses,
            "validator_stakes": {
                addr: str(stake)
                for addr, stake in self.validator_stakes.items()
            },
            "total_staked": str(self.total_staked)
        }