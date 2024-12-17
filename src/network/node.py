# src/network/node.py
import socket
import json
import copy
import threading
import time
from typing import List, Dict, Optional, Tuple, Set
from ..blockchain.blockchain import Blockchain
from ..blockchain.block import Block
from ..blockchain.transaction import Transaction, TransactionType
from ..utils.logger import get_logger

class Node:
    def __init__(
        self,
        host: str,
        port: int,
        blockchain: Optional[Blockchain] = None
    ):
        self.host = host
        self.port = port
        self.blockchain = blockchain or Blockchain()
        self.peers: Set[Tuple[str, int]] = set()
        self.pending_transactions: Set[str] = set()
        
        # Connection management
        self.running = False
        self.server_socket = None
        self.logger = get_logger(__name__)
        
        # Synchronization locks
        self.chain_lock = threading.Lock()
        self.peers_lock = threading.Lock()
        
        # Message handlers
        self.message_handlers = {
            "block": self._handle_block_message,
            "transaction": self._handle_transaction_message,
            "peer_request": self._handle_peer_request,
            "peer_response": self._handle_peer_response,
            "transaction_status": self._handle_transaction_status,
            "node_status": self._handle_node_status,
        }

    def _handle_node_status(self, message: Dict, sender_address: Tuple[str, int]) -> Dict:
        """Handle node status request"""
        try:
            status = {
            "address": f"{self.host}:{self.port}",
            "peers": len(self.peers),
            "chain_length": len(self.blockchain.chain),
            "pending_transactions": len(self.pending_transactions),
            "running": self.running,
            "last_block": self.blockchain.chain[-1].to_dict() if self.blockchain.chain else None
            }
        
            return {
                "type": "node_status_response",
                "data": status
            }
                
        except Exception as e:
            self.logger.error(f"Error handling node status request: {str(e)}")
            return {
                "type": "error",
                "data": {"error": str(e)}
            }
    def start(self):
        """Start the node's server"""
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.logger.info(f"Node listening on {self.host}:{self.port}")
            
            # Start connection handler thread
            connection_handler = threading.Thread(target=self._handle_connections)
            connection_handler.daemon = False
            connection_handler.start()
            
            # Start peer discovery thread
            peer_discovery = threading.Thread(target=self._discover_peers)
            peer_discovery.daemon = False
            peer_discovery.start()
            
            # Keep the main thread alive
            while self.running:
                time.sleep(1)
                
        except Exception as e:
            self.logger.error(f"Failed to start node: {str(e)}")
            self.running = False
            raise

    def stop(self):
        """Stop the node's server"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()

    def _handle_connections(self):
        """Handle incoming connections"""
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, address),
                    daemon=True
                ).start()
            except Exception as e:
                if self.running:
                    self.logger.error(f"Connection handling error: {str(e)}")

    def _handle_client(self, client_socket: socket.socket, address: Tuple[str, int]):
        """Handle individual client connection"""
        try:
            client_socket.settimeout(5)
            data = client_socket.recv(4096)
            if data:
                message = json.loads(data.decode())
                response = self._process_message(message, address)
                if response:
                    client_socket.send(json.dumps(response).encode())
                
        except json.JSONDecodeError:
            self.logger.warning(f"Invalid message from {address}")
        except Exception as e:
            self.logger.error(f"Client handling error: {str(e)}")
        finally:
            client_socket.close()

    def _handle_transaction_status(self, message: Dict, sender_address: Tuple[str, int]) -> Dict:
        """Handle transaction status request"""
        try:
            tx_id = message.get("data", {}).get("tx_id")
            if not tx_id:
                return {
                    "type": "error",
                    "data": {"error": "Missing transaction ID"}
                }
                
            # Check mempool first
            if tx_id in self.pending_transactions:
                status = "pending"
            else:
                # Check blockchain
                status = "unknown"
                with self.chain_lock:
                    for block in self.blockchain.chain:
                        for tx in block.transactions:
                            if tx.transaction_id == tx_id:
                                status = "confirmed"
                                break
                        if status == "confirmed":
                            break
        
            return {
                "type": "transaction_status_response",
                "data": {
                    "status": status,
                    "tx_id": tx_id
                }
            }
                
        except Exception as e:
            self.logger.error(f"Error handling transaction status request: {str(e)}")
            return {
                "type": "error",
                "data": {"error": str(e)}
            }
    def synchronize_with_peer(self, peer_node) -> bool:
        """Synchronize blockchain with peer"""
        with self.chain_lock:
            if len(peer_node.blockchain.chain) <= len(self.blockchain.chain):
                return True
                
            # Create a temporary blockchain for validation
            temp_chain = copy.deepcopy(self.blockchain)
            
            # Try to add each new block
            for block in peer_node.blockchain.chain[len(self.blockchain.chain):]:
                if not temp_chain.add_block(block):
                    return False
                    
            # If all blocks were added successfully, update our blockchain
            self.blockchain = temp_chain
            return True

    def _process_message(self, message: Dict, sender_address: Tuple[str, int]) -> Optional[Dict]:
        """Process received message and return response if needed"""
        message_type = message.get("type")
        if message_type in self.message_handlers:
            try:
                return self.message_handlers[message_type](message, sender_address)
            except Exception as e:
                self.logger.error(f"Error processing {message_type} message: {str(e)}")
        else:
            self.logger.warning(f"Unknown message type: {message_type}")
        return None
    def _handle_block_message(self, message: Dict, sender_address: Tuple[str, int]):
        """Handle received block"""
        block_data = message.get("data")
        if not block_data:
            return
            
        block = Block.from_dict(block_data)
        with self.chain_lock:
            if self.blockchain.add_block(block):
                # Rebroadcast to other peers
                self.broadcast_block(block)

    def _handle_transaction_message(self, message: Dict, sender_address: Tuple[str, int]):
        """Handle received transaction"""
        transaction_data = message.get("data")
        if not transaction_data:
            return
            
        transaction = Transaction.from_dict(transaction_data)
        
        # Check if we've seen this transaction
        if transaction.transaction_id in self.pending_transactions:
            return
            
        # Validate and rebroadcast
        if transaction.verify_transaction(self.blockchain):
            self.broadcast_transaction(transaction)

    def broadcast_block(self, block: Block):
        """Broadcast block to all peers"""
        message = {
            "type": "block",
            "data": block.to_dict()
        }
        self._broadcast_message(message)

    def broadcast_transaction(self, transaction: Transaction):
        """Broadcast transaction to all peers"""
        self.pending_transactions.add(transaction.transaction_id)
        message = {
            "type": "transaction",
            "data": transaction.to_dict()
        }
        self._broadcast_message(message)

    def _broadcast_message(self, message: Dict):
        """Broadcast message to all peers"""
        with self.peers_lock:
            dead_peers = set()
            for peer in self.peers:
                try:
                    self._send_message(peer, message)
                except ConnectionError:
                    dead_peers.add(peer)
                    
            # Remove dead peers
            self.peers -= dead_peers

    def _send_message(self, peer: Tuple[str, int], message: Dict):
        """Send message to specific peer"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect(peer)
            sock.send(json.dumps(message).encode())
        except Exception as e:
            raise ConnectionError(f"Failed to send message to {peer}: {str(e)}")
        finally:
            sock.close()

    def _handle_peer_request(self, message: Dict, sender_address: Tuple[str, int]):
        """Handle peer list request"""
        with self.peers_lock:
            response = {
                "type": "peer_response",
                "data": list(self.peers)
            }
            try:
                self._send_message(sender_address, response)
            except ConnectionError:
                pass

    def _handle_peer_response(self, message: Dict, sender_address: Tuple[str, int]):
        """Handle peer list response"""
        peer_list = message.get("data", [])
        for peer in peer_list:
            self.connect_to_peer(tuple(peer))

    def connect_to_peer(self, peer_address: Tuple[str, int]) -> bool:
        """Connect to new peer"""
        if peer_address == (self.host, self.port):
            return False
            
        with self.peers_lock:
            if peer_address not in self.peers:
                try:
                    self._send_message(peer_address, {"type": "peer_request"})
                    self.peers.add(peer_address)
                    return True
                except ConnectionError:
                    return False
                    
        return False

    def _discover_peers(self):
        """Periodically discover new peers"""
        while self.running:
            try:
                with self.peers_lock:
                    for peer in list(self.peers):
                        try:
                            self._send_message(peer, {"type": "peer_request"})
                        except ConnectionError:
                            self.peers.remove(peer)
            except Exception as e:
                self.logger.error(f"Peer discovery error: {str(e)}")
                
            time.sleep(300)  # Run every 5 minutes

    def get_transaction_status(self, tx_id: str) -> str:
        """Get status of a specific transaction"""
        if tx_id in self.pending_transactions:
            return "pending"
            
        # Check blockchain
        with self.chain_lock:
            for block in self.blockchain.chain:
                for tx in block.transactions:
                    if tx.transaction_id == tx_id:
                        return "confirmed"
        
        return "unknown"

    def get_node_status(self) -> Dict:
        """Get current node status"""
        return {
            "address": f"{self.host}:{self.port}",
            "peers": len(self.peers),
            "chain_length": len(self.blockchain.chain),
            "pending_transactions": len(self.pending_transactions),
            "running": self.running
        }