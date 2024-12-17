# src/testnet/test_transactions.py
import sys
from pathlib import Path
import json
from decimal import Decimal

sys.path.append(str(Path(__file__).parent.parent.parent))

from src.blockchain.transaction import Transaction, TransactionType
from src.wallet.wallet import Wallet

def main():
    # Create test wallets
    wallet1 = Wallet.generate_new()
    wallet2 = Wallet.generate_new()
    
    print(f"Wallet 1 address: {wallet1.address}")
    print(f"Wallet 2 address: {wallet2.address}")
    
    # Create a test transaction
    transaction = Transaction(
        sender=wallet1.address,
        recipient=wallet2.address,
        amount=Decimal("10.0"),
        transaction_type=TransactionType.TRANSFER
    )
    
    print(f"Created transaction: {transaction.transaction_id}")
    
    # Print transaction details
    print("\nTransaction Details:")
    print(f"From: {transaction.sender}")
    print(f"To: {transaction.recipient}")
    print(f"Amount: {transaction.amount}")
    print(f"Type: {transaction.transaction_type.value}")

if __name__ == "__main__":
    main()