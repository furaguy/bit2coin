# src/network/node.py
import socket
import json
import copy
import threading
import time
from typing import List, Dict, Optional, Tuple, Set
from ..blockchain.blockchain import Blockchain
from ..blockchain.block import Block
from ..blockchain.transaction import Transaction
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
            threading.Thread(target=self._handle_connections, daemon=True).start()
            
            # Start peer discovery thread
            threading.Thread(target=self._discover_peers, daemon=True).start()
            
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
            # Set timeout to prevent hanging
            client_socket.settimeout(5)
            
            # Receive data
            data = b""
            while True:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break
                data += chunk
                
            if data:
                message = json.loads(data.decode())
                self._process_message(message, address)
                
        except json.JSONDecodeError:
            self.logger.warning(f"Invalid message from {address}")
        except Exception as e:
            self.logger.error(f"Client handling error: {str(e)}")
        finally:
            client_socket.close()

    def synchronize_with_peer(self, peer_node) -> bool:
        """Synchronize blockchain with peer"""
        with self.chain_lock:
            if len(peer_node.blockchain.chain) <= len(self.blockchain.chain):
                return True  # Already up to date
                
            # Create a temporary blockchain for validation
            temp_chain = copy.deepcopy(self.blockchain)
            
            # Try to add each new block
            for block in peer_node.blockchain.chain[len(self.blockchain.chain):]:
                if not temp_chain.add_block(block):
                    return False
                    
            # If all blocks were added successfully, update our blockchain
            self.blockchain = temp_chain
            return True

    def broadcast_block(self, block: Block):
        """Broadcast block to all peers"""
        message = {
            "type": "block",
            "data": block.to_dict()
        }
        self._broadcast_message(message)

    def broadcast_transaction(self, transaction: Transaction):
        """Broadcast transaction to all peers"""
        # Add to pending set to avoid rebroadcast
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

    def connect_to_peer(self, peer_address: Tuple[str, int]) -> bool:
        """Connect to new peer"""
        if peer_address == (self.host, self.port):
            return False
            
        with self.peers_lock:
            if peer_address not in self.peers:
                # Test connection before adding
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
                # Request peers from known peers
                with self.peers_lock:
                    for peer in list(self.peers):
                        try:
                            self._send_message(peer, {"type": "peer_request"})
                        except ConnectionError:
                            self.peers.remove(peer)
            except Exception as e:
                self.logger.error(f"Peer discovery error: {str(e)}")
                
            time.sleep(300)  # Run every 5 minutes

    def _process_message(self, message: Dict, sender_address: Tuple[str, int]):
        """Process received message"""
        message_type = message.get("type")
        if message_type in self.message_handlers:
            try:
                self.message_handlers[message_type](message, sender_address)
            except Exception as e:
                self.logger.error(f"Error processing {message_type} message: {str(e)}")
        else:
            self.logger.warning(f"Unknown message type: {message_type}")

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
        if transaction.verify():
            self.broadcast_transaction(transaction)

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

    def get_node_status(self) -> Dict:
        """Get current node status"""
        return {
            "address": f"{self.host}:{self.port}",
            "peers": len(self.peers),
            "chain_length": len(self.blockchain.chain),
            "pending_transactions": len(self.pending_transactions)
        }