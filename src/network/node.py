# src/network/node.py

import asyncio
import json
import logging
from typing import Optional, Dict, List, Tuple, Set, Any
from dataclasses import dataclass
import time
from decimal import Decimal
from pathlib import Path
import socket
import struct
import aiofiles
from contextlib import asynccontextmanager

from ..blockchain.blockchain import Blockchain
from ..blockchain.transaction import Transaction
from ..blockchain.block import Block
from ..consensus.proof_of_stake import ProofOfStake
from ..wallet.wallet import Wallet  # For generating node's address
from decimal import Decimal
import logging
logger = logging.getLogger(__name__)

@dataclass
class PeerInfo:
    """Information about a connected peer"""
    node_id: str
    host: str
    port: int
    last_seen: float
    version: str = "1.0.0"
    status: str = "active"

@dataclass
class Message:
    """Network message structure"""
    type: str
    payload: Dict[str, Any]
    sender: str
    timestamp: float = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

    def serialize(self) -> str:
        """Convert message to JSON string"""
        return json.dumps({
            "type": self.type,
            "payload": self.payload,
            "sender": self.sender,
            "timestamp": self.timestamp
        })

    @classmethod
    def deserialize(cls, data: str) -> 'Message':
        """Create message from JSON string"""
        msg_dict = json.loads(data)
        return cls(
            type=msg_dict["type"],
            payload=msg_dict["payload"],
            sender=msg_dict["sender"],
            timestamp=msg_dict.get("timestamp", time.time())
        )

class Node:
    def __init__(
        self,
        host: str,
        port: int,
        blockchain: Optional[Blockchain] = None,
        max_peers: int = 50
    ):
        """Initialize the node"""
        self.host = host
        self.port = port
        
        # Load blockchain state if not provided
        if blockchain is None:
            blockchain = self._load_blockchain_state()
        self.blockchain = blockchain
        
        self.peers: Dict[str, PeerInfo] = {}
        self.server = None
        self.running = False
        self.node_id = f"node_{port}"
        self.max_peers = max_peers

        # Initialize consensus
        self.pos_consensus = self.blockchain.get_pos_consensus() if blockchain else ProofOfStake()
        self.wallet = Wallet.generate_new()  # Create wallet for node
        self.address = self.wallet.address  # Set node address

        # Connection tracking
        self.active_connections: Dict[str, Tuple[asyncio.StreamReader, asyncio.StreamWriter]] = {}
        self.connecting_peers: Set[str] = set()
        self.connection_retries: Dict[str, int] = {}
        self.max_connection_retries = 3
        self.connection_tasks: Set[asyncio.Task] = set()

        # Message queue
        self.message_queue: asyncio.Queue = asyncio.Queue()

        # Set up logging
        self.logger = logging.getLogger(__name__)

        # Background tasks
        self.background_tasks: List[asyncio.Task] = []

        # Message handlers
        self.message_handlers = {
            "handshake": self._handle_handshake,
            "handshake_response": self._handle_handshake_response,
            "transaction": self._handle_transaction,
            "block": self._handle_block,
            "peer_list": self._handle_peer_list,
            "get_blocks": self._handle_get_blocks,
            "get_balance": self._handle_get_balance,
            "node_status": self._handle_node_status,
            "transaction_status": self._handle_transaction_status
        }

    async def _block_production_loop(self):
        """Periodic block production"""
        self.logger = logging.getLogger(__name__)  # Add this line
        self.logger.debug("Starting block production loop")

    
        while self.running:
            self.logger.debug("Block production loop iteration starting")
            try:
                if len(self.blockchain.mempool) > 0:
                    self.logger.debug("Found transactions in mempool, attempting block production")

                    # Get validator for current height
                    current_height = len(self.blockchain.chain)
                    self.logger.debug(f"Current chain height: {current_height}")

                    validator = self.pos_consensus.select_validator(current_height)
                    self.logger.debug(f"Selected validator: {validator}")
                    self.logger.debug(f"Node address: {self.address}")
                    self.logger.debug(f"Active validators: {self.pos_consensus.get_active_validators()}")
                
                    if validator == self.address:
                        self.logger.debug("We are the selected validator, creating block...")
                        # Create reward transaction
                        reward_tx = Transaction.create_reward(
                            recipient=self.address,
                            amount=self.blockchain.get_block_reward(current_height)
                        )
                        self.logger.debug(f"Created reward transaction: {reward_tx.to_dict()}")

                        # Get transactions from mempool (including reward)
                        transactions = [reward_tx] + self.blockchain.mempool[:10]
                        self.logger.debug(f"Selected {len(transactions)} transactions for block")

                        # Create and add block
                        new_block = Block(
                            height=current_height,
                            previous_hash=self.blockchain.chain[-1].hash,
                            transactions=transactions,
                            timestamp=int(time.time()),
                            validator=self.address
                        )
                    
                        if self.blockchain.add_block(new_block):
                            await self.broadcast_block(new_block)
                            self.logger.info(f"Produced new block at height {current_height}")
                        else:
                            self.logger.error("Failed to add new block")
                    else:
                        self.logger.debug("Not selected as validator for this round")
                else:
                    self.logger.debug("No transactions in mempool")                    
            
                # More frequent block production for testing
                await asyncio.sleep(5)  # 5 second block time for testing
            
            except Exception as e:
                self.logger.error(f"Error in block production: {str(e)}", exc_info=True)
                await asyncio.sleep(1)    

    def _load_blockchain_state(self) -> Blockchain:
        """Load blockchain state from file"""
        try:
            state_file = Path("testnet_data/blockchain_state.json")
            if not state_file.exists():
                self.logger.warning("No blockchain state found, creating new blockchain")
                return Blockchain()
                
            self.logger.debug(f"Loading blockchain state from {state_file}")
            with open(state_file, "r") as f:
                state = json.load(f)
                
            blockchain = Blockchain()
            blockchain.import_state(state)
            
            self.logger.debug("Blockchain state loaded successfully")
            return blockchain
            
        except Exception as e:
            self.logger.error(f"Error loading blockchain state: {str(e)}")
            return Blockchain()

    async def start(self):
        """Start the node's server and background tasks"""
        self.logger.debug(f"Starting node on {self.host}:{self.port}")
        self.logger.debug(f"Node address: {self.address}")
        self.logger.debug(f"Initial validator status: active={self.pos_consensus.is_active_validator(self.address)}")
        self.logger.debug(f"Initial active validators: {self.pos_consensus.get_active_validators()}")

        if self.running:
            return

        try:
            self.running = True
        
            # Create and start server
            self.server = await asyncio.start_server(
                self.handle_connection,
                self.host,
                self.port
            )
        
            self.logger.info(f"Node listening on {self.host}:{self.port}")

             # Start block production
            self.background_tasks.append(
                asyncio.create_task(self._block_production_loop())
            )    
        
            # Start background tasks
            self.background_tasks = [
                asyncio.create_task(self._process_message_queue()),
                asyncio.create_task(self._maintain_peers()),
                asyncio.create_task(self._periodic_state_save())
            ]
        
            # Keep server running
            try:
                async with self.server:
                    await self.server.serve_forever()
            except asyncio.CancelledError:
                self.logger.info("Server shutdown requested")
                raise
            except Exception as e:
                self.logger.error(f"Server error: {str(e)}")
                raise
                
        except Exception as e:
            self.running = False
            self.logger.error(f"Failed to start node: {str(e)}")
            raise

    async def stop(self):
        """Stop the node and clean up"""
        try:
            self.running = False
            
            # Cancel background tasks
            for task in self.background_tasks:
                task.cancel()
                
            await asyncio.gather(*self.background_tasks, return_exceptions=True)
            
            # Save final state
            await self._save_blockchain_state()
            
            # Close all connections
            for peer_id, (reader, writer) in self.active_connections.items():
                writer.close()
                await writer.wait_closed()
                
            # Close server
            if self.server:
                self.server.close()
                await self.server.wait_closed()
                
            self.logger.info("Node stopped successfully")
            
        except Exception as e:
            self.logger.error(f"Error stopping node: {str(e)}")

    async def handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle incoming connections"""
        peer_addr = writer.get_extra_info('peername')
        self.logger.debug(f"New connection from {peer_addr}")
        peer_id = None

        try:
            while self.running:
                # Read message length
                length_data = await reader.read(4)
                if not length_data:
                    break

                message_length = int.from_bytes(length_data, 'big')
                if message_length > 10_000_000:  # 10MB limit
                    raise ValueError("Message too large")

                # Read message data
                message_data = await reader.read(message_length)
                if not message_data:
                    break

                # Process message
                message = Message.deserialize(message_data.decode())
                peer_id = message.sender

                # Add to active connections if new peer
                if peer_id and peer_id not in self.active_connections:
                    self.active_connections[peer_id] = (reader, writer)

                # Handle message
                response = await self._handle_message(message)
                if response:
                    response_data = response.serialize().encode()
                    writer.write(len(response_data).to_bytes(4, 'big'))
                    writer.write(response_data)
                    await writer.drain()

        except Exception as e:
            self.logger.error(f"Error handling connection from {peer_addr}: {str(e)}")

        finally:
            # Clean up connection
            if peer_id:
                if peer_id in self.active_connections:
                    del self.active_connections[peer_id]
                if peer_id in self.peers:
                    del self.peers[peer_id]
            writer.close()
            await writer.wait_closed()
            self.logger.debug(f"Connection closed from {peer_addr}")

    async def _handle_message(self, message: Message) -> Optional[Message]:
        """Process incoming messages"""
        try:
            if message.sender in self.peers:
                self.peers[message.sender].last_seen = time.time()

            handler = self.message_handlers.get(message.type)
            if handler:
                response = await handler(message)
                return response
            else:
                self.logger.warning(f"Unknown message type: {message.type}")
                return Message(
                    type="error",
                    payload={"error": "Unknown message type"},
                    sender=self.node_id
                )
        except Exception as e:
            self.logger.error(f"Error handling message: {str(e)}")
            return Message(
                type="error",
                payload={"error": str(e)},
                sender=self.node_id
            )

    async def connect_to_peer(self, address: Tuple[str, int], handshake_data: Optional[Dict] = None) -> bool:
        """Connect to a new peer"""
        if len(self.peers) >= self.max_peers:
            return False

        try:
            reader, writer = await asyncio.open_connection(address[0], address[1])

            # Create handshake message
            if handshake_data is None:
                handshake_data = {
                    "type": "handshake",
                    "payload": {
                        "node_id": self.node_id,
                        "host": self.host,
                        "port": self.port,
                        "version": "1.0.0"
                    },
                    "sender": self.node_id
                }

            # Send handshake
            message = Message(**handshake_data)
            message_data = message.serialize().encode()
            writer.write(len(message_data).to_bytes(4, 'big'))
            writer.write(message_data)
            await writer.drain()

            # Read response
            length_data = await reader.read(4)
            if not length_data:
                return False

            message_length = int.from_bytes(length_data, 'big')
            response_data = await reader.read(message_length)

            if response_data:
                response = Message.deserialize(response_data.decode())
                if response.type == "handshake_response" and response.payload.get("status") == "accepted":
                    peer_id = response.sender
                    
                    # Store peer info
                    self.peers[peer_id] = PeerInfo(
                        node_id=peer_id,
                        host=address[0],
                        port=address[1],
                        last_seen=time.time()
                    )
                    
                    # Store connection
                    self.active_connections[peer_id] = (reader, writer)

                    # Create connection handling task
                    task = asyncio.create_task(self._handle_peer_connection(peer_id, reader, writer))
                    self.connection_tasks.add(task)
                    task.add_done_callback(self.connection_tasks.discard)

                    return True

            return False

        except Exception as e:
            self.logger.error(f"Failed to connect to peer {address}: {str(e)}")
            return False

    async def _handle_peer_connection(self, peer_id: str, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle ongoing peer connection"""
        try:
            while self.running:
                # Read message length
                length_data = await reader.read(4)
                if not length_data:
                    break

                message_length = int.from_bytes(length_data, 'big')
                if message_length > 10_000_000:  # 10MB limit
                    break

                # Read message
                message_data = await reader.read(message_length)
                if not message_data:
                    break

                # Process message
                message = Message.deserialize(message_data.decode())
                await self._handle_message(message)

                # Update last seen
                if peer_id in self.peers:
                    self.peers[peer_id].last_seen = time.time()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"Error handling peer connection {peer_id}: {str(e)}")
        finally:
            # Clean up connection
            if peer_id in self.active_connections:
                del self.active_connections[peer_id]
            if peer_id in self.peers:
                del self.peers[peer_id]
            writer.close()
            await writer.wait_closed()

    # Background Tasks
    async def _process_message_queue(self):
        """Process messages from queue"""
        while self.running:
            try:
                message = await self.message_queue.get()
                await self._handle_message(message)
                self.message_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error processing message from queue: {str(e)}")
                await asyncio.sleep(1)

    async def _maintain_peers(self):
        """Maintain peer connections"""
        while self.running:
            try:
                current_time = time.time()
                inactive_peers = [
                    peer_id for peer_id, peer in self.peers.items()
                    if current_time - peer.last_seen > 300  # 5 minutes timeout
                ]

                for peer_id in inactive_peers:
                    if peer_id in self.active_connections:
                        reader, writer = self.active_connections[peer_id]
                        writer.close()
                        await writer.wait_closed()
                        del self.active_connections[peer_id]
                    del self.peers[peer_id]

                await asyncio.sleep(60)  # Check every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in peer maintenance: {str(e)}")
                await asyncio.sleep(60)

    async def _periodic_state_save(self):
        """Periodically save blockchain state"""
        while self.running:
            try:
                await self._save_blockchain_state()
                await asyncio.sleep(300)  # Save every 5 minutes
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error saving blockchain state: {str(e)}")
                await asyncio.sleep(60)

    async def _save_blockchain_state(self):
        """Save blockchain state to file"""
        try:
            if not hasattr(self, 'blockchain') or not self.blockchain:
                return

            state = self.blockchain.export_state()
            
            # Create directory if it doesn't exist
            Path("testnet_data").mkdir(exist_ok=True)
            
            state_file = Path("testnet_data/blockchain_state.json")
            async with aiofiles.open(state_file, "w") as f:
                await f.write(json.dumps(state, indent=2))
                
            self.logger.debug("Blockchain state saved successfully")
            
        except Exception as e:
            self.logger.error(f"Error saving blockchain state: {str(e)}")

    # Message Handlers
    async def _handle_handshake(self, message: Message) -> Message:
        """Handle peer handshake"""
        try:
            peer_info = PeerInfo(
                node_id=message.sender,
                host=message.payload.get("host", "127.0.0.1"),
                port=message.payload.get("port", 0),
                last_seen=time.time(),
                version=message.payload.get("version", "1.0.0")
            )
        
            self.peers[message.sender] = peer_info
        
            return Message(
                type="handshake_response",
                payload={
                    "status": "accepted",
                    "node_id": self.node_id,
                    "host": self.host,
                    "port": self.port,
                    "version": "1.0.0"
                },
                sender=self.node_id
            )
            
        except Exception as e:
            self.logger.error(f"Error handling handshake: {str(e)}")
            return Message(
                type="handshake_response",
                payload={
                    "status": "error",
                    "reason": str(e)
                },
                sender=self.node_id
            )

    async def _handle_handshake_response(self, message: Message) -> Optional[Message]:
        """Handle handshake response"""
        try:
            if message.payload.get("status") == "accepted":
                peer_info = PeerInfo(
                    node_id=message.sender,
                    host=message.payload.get("host", "127.0.0.1"),
                    port=message.payload.get("port", 0),
                    last_seen=time.time(),
                    version=message.payload.get("version", "1.0.0")
                )
                self.peers[message.sender] = peer_info
            return None
        except Exception as e:
            self.logger.error(f"Error handling handshake response: {str(e)}")
            return None

    async def _handle_transaction(self, message: Message) -> Message:
        """Handle incoming transaction"""
        try:
            tx_data = message.payload.get("transaction", {})
            self.logger.debug(f"Received transaction data: {tx_data}")
            
            transaction = Transaction.from_dict(tx_data)
            self.logger.debug(f"Transaction parsed: {transaction.transaction_id}")

            # Verify and process transaction
            self.logger.debug(f"Verifying transaction from {transaction.sender} to {transaction.recipient}")
            if transaction.verify_transaction(self.blockchain):
                self.logger.debug("Transaction verification succeeded")
                if self.blockchain:
                    self.blockchain.add_transaction_to_mempool(transaction)
                    self.logger.debug("Transaction added to mempool")

                # Broadcast to peers if needed
                if message.payload.get("propagate", True):
                    await self._propagate_message(message, exclude=message.sender)
                    self.logger.debug("Transaction propagated to peers")

                return Message(
                    type="transaction_response",
                    payload={
                        "status": "accepted",
                        "tx_id": transaction.transaction_id
                    },
                    sender=self.node_id
                )
            else:
                self.logger.warning(f"Transaction verification failed for sender {transaction.sender}")
                return Message(
                    type="transaction_response",
                    payload={
                        "status": "rejected",
                        "reason": "Invalid transaction"
                    },
                    sender=self.node_id
                )

        except Exception as e:
            self.logger.error(f"Error handling transaction: {str(e)}", exc_info=True)
            return Message(
                type="transaction_response",
                payload={
                    "status": "error",
                    "reason": str(e)
                },
                sender=self.node_id
            )

    async def _handle_block(self, message: Message) -> Message:
        """Handle incoming block"""
        try:
            block_data = message.payload.get("block", {})
            block = Block.from_dict(block_data)
        
            if self.blockchain.add_block(block):
                # Save state after successful block addition
                await self._save_blockchain_state()

                # Broadcast to peers if needed
                if message.payload.get("propagate", True):
                    await self._propagate_message(message, exclude=message.sender)
                
                return Message(
                    type="block_response",
                    payload={
                        "status": "accepted",
                        "block_hash": block.hash
                    },
                    sender=self.node_id
                )
            else:
                return Message(
                    type="block_response",
                    payload={
                        "status": "rejected",
                        "reason": "Invalid block"
                    },
                    sender=self.node_id
                )
                
        except Exception as e:
            self.logger.error(f"Error handling block: {str(e)}")
            return Message(
                type="block_response",
                payload={
                    "status": "error",
                    "reason": str(e)
                },
                sender=self.node_id
            )

    async def _handle_get_blocks(self, message: Message) -> Message:
        """Handle block request"""
        try:
            start_height = message.payload.get("start_height", 0)
            end_height = message.payload.get("end_height", len(self.blockchain.chain) - 1)
        
            blocks = []
            for height in range(start_height, min(end_height + 1, len(self.blockchain.chain))):
                block = self.blockchain.chain[height]
                blocks.append(block.to_dict())
        
            return Message(
                type="blocks_response",
                payload={"blocks": blocks},
                sender=self.node_id
            )
        except Exception as e:
            return Message(
                type="blocks_response",
                payload={
                    "status": "error",
                    "reason": str(e)
                },
                sender=self.node_id
            )

    async def _handle_get_balance(self, message: Message) -> Message:
        """Handle balance request"""
        try:
            address = message.payload["address"]
            balance = self.blockchain.get_balance(address)
        
            return Message(
                type="balance_response",
                payload={
                    "status": "success",
                    "balance": str(balance),
                    "address": address
                },
                sender=self.node_id
            )
        except Exception as e:
            return Message(
                type="balance_response",
                payload={
                    "status": "error",
                    "reason": str(e)
                },
                sender=self.node_id
            )

    async def _handle_transaction_status(self, message: Message) -> Message:
        """Handle transaction status request"""
        try:
            tx_id = message.payload["tx_id"]
            status = await self.get_transaction_status(tx_id)
        
            return Message(
                type="transaction_status_response",
                payload=status,
                sender=self.node_id
            )
            
        except Exception as e:
            self.logger.error(f"Error handling transaction status request: {str(e)}")
            return Message(
                type="transaction_status_response",
                payload={
                    "status": "error",
                    "reason": str(e)
                },
                sender=self.node_id
            )

    async def _handle_peer_list(self, message: Message) -> Message:
        """Handle peer list request"""
        try:
            peer_list = [
                {
                    "node_id": peer_id,
                    "host": peer.host,
                    "port": peer.port,
                    "version": peer.version
                }
                for peer_id, peer in self.peers.items()
            ]
        
            return Message(
                type="peer_list_response",
                payload={"peers": peer_list},
                sender=self.node_id
            )
        except Exception as e:
            return Message(
                type="peer_list_response",
                payload={
                    "status": "error",
                    "reason": str(e)
                },
                sender=self.node_id
            )

    async def _handle_node_status(self, message: Message) -> Message:
        """Handle node status request"""
        try:
            status = {
                "blockchain_height": len(self.blockchain.chain),
                "peers": len(self.peers),
                "node_id": self.node_id,
                "uptime": time.time() - getattr(self, 'start_time', time.time())
            }
        
            return Message(
                type="status_response",
                payload=status,
                sender=self.node_id
            )
        except Exception as e:
            return Message(
                type="status_response",
                payload={
                    "status": "error",
                    "reason": str(e)
                },
                sender=self.node_id
            )

    # Utility Methods
    async def _propagate_message(self, message: Message, exclude: Optional[str] = None) -> None:
        """Propagate message to all peers except excluded one"""
        for peer_id, (_, writer) in self.active_connections.items():
            if peer_id != exclude:
                try:
                    message_data = message.serialize().encode()
                    writer.write(len(message_data).to_bytes(4, 'big'))
                    writer.write(message_data)
                    await writer.drain()
                except Exception as e:
                    self.logger.error(f"Error propagating message to peer {peer_id}: {str(e)}")

    # Public Interface
    def broadcast_transaction(self, transaction: Transaction):
        """Broadcast transaction to all peers"""
        message = Message(
            type="transaction",
            payload={
                "transaction": transaction.to_dict(),
                "propagate": True
            },
            sender=self.node_id
        )
        asyncio.create_task(self._propagate_message(message))

    def broadcast_block(self, block: Block):
        """Broadcast block to all peers"""
        message = Message(
            type="block",
            payload={
                "block": block.to_dict(),
                "propagate": True
            },
            sender=self.node_id
        )
        asyncio.create_task(self._propagate_message(message))

    async def get_transaction_status(self, tx_id: str) -> Dict:
        """Get transaction status and confirmations"""
        try:
            # Get block info for transaction
            block_info = self.blockchain.get_transaction_block(tx_id)
            if block_info:
                confirmations = len(self.blockchain.chain) - block_info['height']
                return {
                    "status": "confirmed",
                    "confirmations": confirmations,
                    "block_height": block_info['height'],
                    "block_hash": block_info['hash']
                }
            
            # Check if transaction is in mempool
            if any(tx.transaction_id == tx_id for tx in self.blockchain.mempool):
                return {
                    "status": "pending",
                    "confirmations": 0
                }
            
            return {
                "status": "unknown",
                "confirmations": 0
            }
        
        except Exception as e:
            self.logger.error(f"Error getting transaction status: {str(e)}")
            return {
                "status": "error",
                "confirmations": 0
            }    

    def get_node_info(self) -> Dict:
        """Get node information"""
        return {
            "node_id": self.node_id,
            "address": f"{self.host}:{self.port}",
            "peers": len(self.peers),
            "blockchain_height": len(self.blockchain.chain),
            "uptime": time.time() - getattr(self, 'start_time', time.time()),
            "running": self.running
        }