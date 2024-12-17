# src/testnet/test_transactions.py
import sys
from pathlib import Path
import json
from decimal import Decimal
import time
import socket
import logging
from typing import Dict, Tuple, List, Optional

sys.path.append(str(Path(__file__).parent.parent.parent))

from src.blockchain.transaction import Transaction, TransactionType
from src.wallet.wallet import Wallet

class TestnetClient:
    def __init__(self, base_port: int = 6000, num_nodes: int = 3):
        self.base_port = base_port
        self.num_nodes = num_nodes
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("testnet-client")

    def broadcast_transaction(self, transaction: Transaction) -> bool:
        """Broadcast transaction to all nodes"""
        message = {
            "type": "transaction",
            "data": transaction.to_dict()
        }
        
        results = []
        for port in range(self.base_port, self.base_port + self.num_nodes):
            try:
                self._send_to_node(port, message)
                print(f"Transaction broadcast to node on port {port}")
                results.append(True)
            except Exception as e:
                print(f"Failed to broadcast to node on port {port}: {str(e)}")
                results.append(False)
        return all(results)

    def _send_to_node(self, port: int, message: dict):
        """Send message to a specific node"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(5)
            sock.connect(("127.0.0.1", port))
            sock.send(json.dumps(message).encode())
            time.sleep(0.1)  # Small delay to ensure message is sent
        finally:
            sock.close()

    def get_node_status(self, port: int) -> Dict:
        """Get status of a specific node"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(5)
            sock.connect(("127.0.0.1", port))
            
            # Send status request
            message = {
                "type": "node_status",
                "data": {}
            }
            sock.send(json.dumps(message).encode())
            
            # Wait for response
            response = sock.recv(4096)
            if response:
                response_data = json.loads(response.decode())
                return response_data.get("data", {})
            return {"error": "no response"}
            
        except socket.timeout:
            return {"error": "timeout"}
        except Exception as e:
            return {"error": str(e)}
        finally:
            sock.close()

    def check_transaction_status(self, tx_id: str) -> Dict[int, str]:
        """Check transaction status across all nodes"""
        statuses = {}
        for port in range(self.base_port, self.base_port + self.num_nodes):
            try:
                status = self._get_transaction_status(port, tx_id)
                print(f"Node on port {port}: Transaction status = {status}")
                statuses[port] = status
            except Exception as e:
                print(f"Failed to get status from node on port {port}: {str(e)}")
                statuses[port] = "error"
        return statuses

    def _get_transaction_status(self, port: int, tx_id: str) -> str:
        """Get transaction status from a specific node"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(5)
            sock.connect(("127.0.0.1", port))
            
            message = {
                "type": "transaction_status",
                "data": {"tx_id": tx_id}
            }
            sock.send(json.dumps(message).encode())
            
            response = sock.recv(4096)
            if response:
                response_data = json.loads(response.decode())
                return response_data.get("status", "unknown")
            return "no response"
            
        except socket.timeout:
            return "timeout"
        except Exception as e:
            return f"error: {str(e)}"
        finally:
            sock.close()

def main():
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    try:
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

        # Create client and broadcast transaction
        print("\nBroadcasting transaction to testnet nodes...")
        client = TestnetClient()
        
        # Check node status before broadcasting
        print("\nChecking node status before broadcast:")
        for port in range(6000, 6003):
            status = client.get_node_status(port)
            print(f"Node on port {port} status: {json.dumps(status, indent=2)}")

        # Broadcast transaction
        if client.broadcast_transaction(transaction):
            print("\nTransaction successfully broadcast to all nodes")
        else:
            print("\nWarning: Transaction may not have reached all nodes")

        # Monitor transaction propagation
        print("\nMonitoring transaction status:")
        for _ in range(3):  # Check 3 times
            statuses = client.check_transaction_status(transaction.transaction_id)
            if all(status == "confirmed" for status in statuses.values()):
                print("Transaction confirmed by all nodes!")
                break
            time.sleep(2)

        # Final node status check
        print("\nFinal node status check:")
        for port in range(6000, 6003):
            status = client.get_node_status(port)
            print(f"Node on port {port} status: {json.dumps(status, indent=2)}")

    except Exception as e:
        logger.error(f"Error in test transaction: {str(e)}")
        logger.exception(e)

if __name__ == "__main__":
    main()