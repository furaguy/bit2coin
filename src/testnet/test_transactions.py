# src/testnet/test_transactions.py
import sys
from pathlib import Path
import json
from decimal import Decimal
import time
import socket

sys.path.append(str(Path(__file__).parent.parent.parent))

from src.blockchain.transaction import Transaction, TransactionType
from src.wallet.wallet import Wallet

class TestnetClient:
    def __init__(self, base_port: int = 6000, num_nodes: int = 3):
        self.base_port = base_port
        self.num_nodes = num_nodes

    def broadcast_transaction(self, transaction: Transaction):
        """Broadcast transaction to all nodes"""
        message = {
            "type": "transaction",
            "data": transaction.to_dict()
        }
        
        for port in range(self.base_port, self.base_port + self.num_nodes):
            try:
                self._send_to_node(port, message)
                print(f"Transaction broadcast to node on port {port}")
            except Exception as e:
                print(f"Failed to broadcast to node on port {port}: {str(e)}")

    def _send_to_node(self, port: int, message: dict):
        """Send message to a specific node"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect(("127.0.0.1", port))
            sock.send(json.dumps(message).encode())
        finally:
            sock.close()

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
    
    print(f"\nCreated transaction: {transaction.transaction_id}")
    
    # Print transaction details
    print("\nTransaction Details:")
    print(f"From: {transaction.sender}")
    print(f"To: {transaction.recipient}")
    print(f"Amount: {transaction.amount}")
    print(f"Type: {transaction.transaction_type.value}")

    # Broadcast transaction to testnet nodes
    print("\nBroadcasting transaction to testnet nodes...")
    client = TestnetClient()
    client.broadcast_transaction(transaction)

    # Wait a moment and then check transaction status
    print("\nWaiting for transaction propagation...")
    time.sleep(5)

if __name__ == "__main__":
    main()