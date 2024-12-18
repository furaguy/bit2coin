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
        """Initialize node"""
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
        
        # Thread tracking
        self.connection_handler_thread = None
        self.peer_discovery_thread = None
        self.health_check_thread = None
        
        # Thread events for graceful shutdown
        self.shutdown_event = threading.Event()
        
        # Message handlers
        self.message_handlers = {
            "block": self._handle_block_message,
            "transaction": self._handle_transaction_message,
            "peer_request": self._handle_peer_request,
            "peer_response": self._handle_peer_response,
            "transaction_status": self._handle_transaction_status,
            "node_status": self._handle_node_status,
            "sync_request": self._handle_sync_request,
            "sync_response": self._handle_sync_response,
        }

    def start(self, init_only: bool = False):
        """Start the node's server
        
        Args:
            init_only: If True, just initialize the socket but don't start background threads
        """
        try:
            if self.running:
                self.logger.warning(f"Node {self.port} is already running")
                return

            self.running = True
            self.shutdown_event.clear()
            self.logger.info(f"Starting node on {self.host}:{self.port}")
            
            # Create and configure socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Bind socket
            self.logger.info(f"Binding socket to {self.host}:{self.port}")
            self.server_socket.bind((self.host, self.port))
            
            # Start listening
            self.logger.info(f"Starting to listen on {self.host}:{self.port}")
            self.server_socket.listen(5)
            self.server_socket.settimeout(1)  # Add timeout for graceful shutdown
            self.logger.info(f"Node successfully listening on {self.host}:{self.port}")
            
            if not init_only:
                # Start threads only if not in init_only mode
                self.connection_handler_thread = threading.Thread(
                    target=self._handle_connections,
                    name=f"ConnectionHandler-{self.port}",
                    daemon=True
                )
                self.connection_handler_thread.start()
                
                self.health_check_thread = threading.Thread(
                    target=self._run_health_checks,
                    name=f"HealthCheck-{self.port}",
                    daemon=True
                )
                self.health_check_thread.start()
            
        except Exception as e:
            self.logger.error(f"Failed to start node: {str(e)}")
            self.running = False
            self.shutdown_event.set()
            raise

    def stop(self):
        """Stop the node's server"""
        try:
            self.logger.info(f"Stopping node on {self.host}:{self.port}")
            self.running = False
            self.shutdown_event.set()
            
            # Close server socket
            if self.server_socket:
                try:
                    self.server_socket.close()
                    self.logger.info("Server socket closed successfully")
                except Exception as e:
                    self.logger.error(f"Error closing server socket: {str(e)}")
            
            # Let threads finish naturally (they're daemon threads)
            time.sleep(1)  # Give threads time to notice shutdown event
            
            # Clear thread references
            self.connection_handler_thread = None
            self.health_check_thread = None
            
            # Clear peer connections
            with self.peers_lock:
                self.peers.clear()
            
            self.logger.info(f"Node {self.port} stopped successfully")
            
        except Exception as e:
            self.logger.error(f"Error stopping node: {str(e)}")
            raise

    def is_healthy(self) -> bool:
        """Check if node is healthy"""
        return (
            self.running and 
            not self.shutdown_event.is_set() and
            self.server_socket is not None and
            (self.connection_handler_thread is None or self.connection_handler_thread.is_alive()) and
            (self.health_check_thread is None or self.health_check_thread.is_alive())
        )

    def _handle_connections(self):
        """Handle incoming connections"""
        self.logger.info(f"Connection handler started for node {self.port}")
        while not self.shutdown_event.is_set():
            try:
                try:
                    client_socket, address = self.server_socket.accept()
                    self.logger.debug(f"New connection from {address}")
                    
                    client_handler = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, address),
                        name=f"ClientHandler-{address[1]}",
                        daemon=True
                    )
                    client_handler.start()
                    
                except socket.timeout:
                    # This is expected due to the socket timeout we set
                    continue
                    
            except Exception as e:
                if self.running and not self.shutdown_event.is_set():
                    self.logger.error(f"Connection handling error: {str(e)}")
                    time.sleep(1)

    def _handle_client(self, client_socket: socket.socket, address: Tuple[str, int]):
        """Handle individual client connection"""
        try:
            client_socket.settimeout(5)
            data = client_socket.recv(4096)
            if data:
                message = json.loads(data.decode())
                self.logger.debug(f"Received message from {address}: {message.get('type')}")
                
                response = self._process_message(message, address)
                if response:
                    response_data = json.dumps(response).encode()
                    client_socket.send(response_data)
                    self.logger.debug(f"Sent response to {address}: {response.get('type')}")
                
        except json.JSONDecodeError:
            self.logger.warning(f"Invalid JSON message from {address}")
        except socket.timeout:
            self.logger.debug(f"Connection timeout from {address}")
        except Exception as e:
            self.logger.error(f"Client handling error from {address}: {str(e)}")
        finally:
            try:
                client_socket.close()
                self.logger.debug(f"Closed connection from {address}")
            except Exception as e:
                self.logger.error(f"Error closing client socket: {str(e)}")

    def connect_to_peer(self, peer_address: Tuple[str, int]) -> bool:
        """Connect to a new peer"""
        try:
            if peer_address == (self.host, self.port):
                return False  # Don't connect to self
                
            with self.peers_lock:
                if peer_address in self.peers:
                    return False  # Already connected
                
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect(peer_address)
            
            message = {
                "type": "peer_request",
                "data": {}
            }
            sock.send(json.dumps(message).encode())
            
            with self.peers_lock:
                self.peers.add(peer_address)
            
            self.logger.info(f"Connected to peer {peer_address}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error connecting to peer {peer_address}: {str(e)}")
            return False
        finally:
            sock.close()

    def _process_message(self, message: Dict, sender_address: Tuple[str, int]) -> Optional[Dict]:
        """Process received message and return response if needed"""
        try:
            message_type = message.get("type")
            if message_type in self.message_handlers:
                try:
                    response = self.message_handlers[message_type](message, sender_address)
                    if response:
                        response.setdefault("type", f"{message_type}_response")
                    return response
                except Exception as e:
                    self.logger.error(f"Error processing {message_type} message: {str(e)}")
                    return {
                        "type": "error",
                        "data": {"error": f"Error processing {message_type}: {str(e)}"}
                    }
            else:
                self.logger.warning(f"Unknown message type: {message_type}")
                return {
                    "type": "error",
                    "data": {"error": f"Unknown message type: {message_type}"}
                }
        except Exception as e:
            self.logger.error(f"Error in message processing: {str(e)}")
            return {
                "type": "error",
                "data": {"error": str(e)}
            }

    def _handle_block_message(self, message: Dict, sender_address: Tuple[str, int]) -> Optional[Dict]:
        """Handle incoming block message"""
        try:
            block_data = message.get("data")
            if not block_data:
                return {"type": "error", "data": {"error": "No block data provided"}}
            
            # Convert dictionary to Block object
            block = Block(**block_data)
            
            # Validate and add block to blockchain
            if self.blockchain and self.blockchain.add_block(block):
                self.logger.info(f"Added new block at height {block.height}")
                return {
                    "type": "block_response",
                    "data": {"status": "accepted", "height": block.height}
                }
            else:
                return {
                    "type": "block_response",
                    "data": {"status": "rejected", "reason": "Invalid block"}
                }
                
        except Exception as e:
            self.logger.error(f"Error handling block message: {str(e)}")
            return {
                "type": "error",
                "data": {"error": f"Block processing failed: {str(e)}"}
            }

    def _handle_transaction_message(self, message: Dict, sender_address: Tuple[str, int]) -> Optional[Dict]:
        """Handle incoming transaction message"""
        try:
            tx_data = message.get("data")
            if not tx_data:
                return {"type": "error", "data": {"error": "No transaction data provided"}}
            
            # Convert dictionary to Transaction object
            transaction = Transaction.from_dict(tx_data)
            
            # Add to blockchain's mempool
            if self.blockchain and self.blockchain.add_transaction_to_mempool(transaction):
                self.logger.info(f"Added transaction {transaction.transaction_id} to mempool")
                return {
                    "type": "transaction_response",
                    "data": {"status": "accepted", "tx_id": transaction.transaction_id}
                }
            else:
                return {
                    "type": "transaction_response",
                    "data": {"status": "rejected", "reason": "Invalid transaction"}
                }
                
        except Exception as e:
            self.logger.error(f"Error handling transaction message: {str(e)}")
            return {
                "type": "error",
                "data": {"error": f"Transaction processing failed: {str(e)}"}
            }

    def _handle_peer_request(self, message: Dict, sender_address: Tuple[str, int]) -> Optional[Dict]:
        """Handle peer list request"""
        try:
            with self.peers_lock:
                peer_list = list(self.peers)
            return {
                "type": "peer_response",
                "data": {"peers": peer_list}
            }
        except Exception as e:
            self.logger.error(f"Error handling peer request: {str(e)}")
            return {
                "type": "error",
                "data": {"error": f"Peer list request failed: {str(e)}"}
            }

    def _handle_peer_response(self, message: Dict, sender_address: Tuple[str, int]) -> None:
        """Handle peer list response"""
        try:
            peers = message.get("data", {}).get("peers", [])
            for peer in peers:
                with self.peers_lock:
                    if peer not in self.peers:
                        self.peers.add(tuple(peer))
        except Exception as e:
            self.logger.error(f"Error handling peer response: {str(e)}")

    def _handle_transaction_status(self, message: Dict, sender_address: Tuple[str, int]) -> Optional[Dict]:
        """Handle transaction status request"""
        try:
            tx_id = message.get("data", {}).get("tx_id")
            if not tx_id:
                return {"type": "error", "data": {"error": "No transaction ID provided"}}
            
            if tx_id in self.pending_transactions:
                return {
                    "type": "transaction_status_response",
                    "data": {"status": "pending", "tx_id": tx_id}
                }
            
            if self.blockchain and self.blockchain.get_transaction(tx_id):
                return {
                    "type": "transaction_status_response",
                    "data": {"status": "confirmed", "tx_id": tx_id}
                }
            
            return {
                "type": "transaction_status_response",
                "data": {"status": "unknown", "tx_id": tx_id}
            }
                
        except Exception as e:
            self.logger.error(f"Error handling transaction status request: {str(e)}")
            return {
                "type": "error",
                "data": {"error": f"Transaction status request failed: {str(e)}"}
            }

    def _handle_sync_request(self, message: Dict, sender_address: Tuple[str, int]) -> Optional[Dict]:
        """Handle blockchain sync request"""
        try:
            start_height = message.get("data", {}).get("start_height")
            end_height = message.get("data", {}).get("end_height")
            
            if start_height is None or end_height is None:
                return {
                    "type": "error",
                    "data": {"error": "Invalid sync request parameters"}
                }

            blocks = []
            with self.chain_lock:
                for height in range(start_height, end_height + 1):
                    block = self.blockchain.get_block_by_height(height)
                    if block:
                        blocks.append(block.to_dict())

            return {
                "type": "sync_response",
                "data": {
                    "blocks": blocks,
                    "start_height": start_height,
                    "end_height": end_height
                }
            }

        except Exception as e:
            self.logger.error(f"Error handling sync request: {str(e)}")
            return {
                "type": "error",
                "data": {"error": f"Sync request failed: {str(e)}"}
            }

    def _handle_sync_response(self, message: Dict, sender_address: Tuple[str, int]) -> None:
        """Handle blockchain sync response"""
        try:
            data = message.get("data", {})
            blocks = data.get("blocks", [])
            
            with self.chain_lock:
                for block_data in blocks:
                    block = Block(**block_data)
                    if not self.blockchain.has_block(block.hash):
                        if self.blockchain.add_block(block):
                            self.logger.info(f"Added synced block at height {block.height}")
                        else:
                            self.logger.warning(f"Failed to add synced block at height {block.height}")
                            break

        except Exception as e:
            self.logger.error(f"Error handling sync response: {str(e)}")

    def _handle_node_status(self, message: Dict, sender_address: Tuple[str, int]) -> Optional[Dict]:
        """Handle node status request"""
        try:
            status = {
                "address": f"{self.host}:{self.port}",
                "running": self.running,
                "peer_count": len(self.peers),
                "pending_transactions": len(self.pending_transactions),
                "blockchain_height": len(self.blockchain.chain) if self.blockchain else 0
            }
            return {
                "type": "node_status_response",
                "data": status
            }
        except Exception as e:
            self.logger.error(f"Error handling node status request: {str(e)}")
            return {
                "type": "error",
                "data": {"error": f"Node status request failed: {str(e)}"}
            }

    def _run_health_checks(self):
        """Run periodic health checks"""
        self.logger.info(f"Starting health check thread for node {self.port}")
        last_status_log = 0
        
        while not self.shutdown_event.is_set():
            try:
                current_time = time.time()
                
                # Basic health checks
                if not self.server_socket:
                    self.logger.error("Server socket is not initialized")
                    break
                    
                if (self.connection_handler_thread is not None and 
                    not self.connection_handler_thread.is_alive()):
                    self.logger.error("Connection handler thread died")
                    break

                # Check peer connections
                with self.peers_lock:
                    if len(self.peers) == 0:
                        self.logger.warning("No peer connections")
                    
                # Log status periodically
                if current_time - last_status_log > 60:
                    status = self.get_node_status()
                    self.logger.info(f"Node health check - Status: {status}")
                    last_status_log = current_time
                    
                time.sleep(10)  # Sleep between checks
                
            except Exception as e:
                self.logger.error(f"Health check failed: {str(e)}")
                break

    def get_node_status(self) -> Dict:
        """Get current node status"""
        return {
            "address": f"{self.host}:{self.port}",
            "running": self.running,
            "peer_count": len(self.peers),
            "pending_transactions": len(self.pending_transactions),
            "blockchain_height": len(self.blockchain.chain) if self.blockchain else 0
        }

    def broadcast_transaction(self, transaction: Transaction) -> bool:
        """Broadcast transaction to all peers"""
        message = {
            "type": "transaction",
            "data": transaction.to_dict()
        }
        
        success = True
        with self.peers_lock:
            for peer in self.peers:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(5)
                    sock.connect(peer)
                    sock.send(json.dumps(message).encode())
                    sock.close()
                except Exception as e:
                    self.logger.error(f"Failed to broadcast transaction to {peer}: {str(e)}")
                    success = False
                    
        return success

    def broadcast_block(self, block: Block) -> bool:
        """Broadcast block to all peers"""
        message = {
            "type": "block",
            "data": block.to_dict()
        }
        
        success = True
        with self.peers_lock:
            for peer in self.peers:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(5)
                    sock.connect(peer)
                    sock.send(json.dumps(message).encode())
                    sock.close()
                except Exception as e:
                    self.logger.error(f"Failed to broadcast block to {peer}: {str(e)}")
                    success = False
                    
        return success                    