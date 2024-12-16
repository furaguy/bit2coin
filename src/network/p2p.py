# src/network/p2p.py

import asyncio
import json
import logging
from typing import Dict, Set, Optional, List
import websockets
from dataclasses import dataclass, asdict
from enum import Enum
import time
import random
from websockets.exceptions import ConnectionClosed
import socket
import struct
from contextlib import asynccontextmanager

from src.blockchain.block import Block
from src.blockchain.transaction import Transaction
from src.storage.blockchain_state import BlockchainState
from src.blockchain.mempool import TransactionMemPool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MessageType(Enum):
    """Enumeration of message types in the P2P network"""
    HANDSHAKE = "handshake"
    PEER_LIST = "peer_list"
    NEW_BLOCK = "new_block"
    NEW_TRANSACTION = "new_transaction"
    BLOCK_REQUEST = "block_request"
    BLOCK_RESPONSE = "block_response"
    SYNC_REQUEST = "sync_request"
    SYNC_RESPONSE = "sync_response"
    PING = "ping"
    PONG = "pong"

@dataclass
class PeerInfo:
    """Information about a peer node"""
    node_id: str
    address: str
    port: int
    last_seen: float
    version: str
    capabilities: List[str]
    last_block_height: Optional[int] = None
    
    def is_active(self, timeout: int = 300) -> bool:
        """Check if peer is considered active"""
        return time.time() - self.last_seen < timeout

@dataclass
class Message:
    """Network message structure"""
    type: MessageType
    payload: dict
    sender: str
    timestamp: float = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

    def serialize(self) -> str:
        """Convert message to JSON string"""
        return json.dumps({
            "type": self.type.value,
            "payload": self.payload,
            "sender": self.sender,
            "timestamp": self.timestamp
        })

    @classmethod
    def deserialize(cls, data: str) -> 'Message':
        """Create message from JSON string"""
        msg_dict = json.loads(data)
        return cls(
            type=MessageType(msg_dict["type"]),
            payload=msg_dict["payload"],
            sender=msg_dict["sender"],
            timestamp=msg_dict["timestamp"]
        )

class P2PNode:
    """P2P Network Node implementation"""
    
    def __init__(self, 
                 host: str, 
                 port: int, 
                 blockchain_state: BlockchainState,
                 mempool: TransactionMemPool,
                 node_id: str = None, 
                 version: str = "1.0.0",
                 max_peers: int = 50):
        """Initialize P2P node"""
        self.host = host
        self.port = port
        self.blockchain_state = blockchain_state
        self.mempool = mempool
        self.node_id = node_id or self._generate_node_id()
        self.version = version
        self.max_peers = max_peers
        self.peers: Dict[str, PeerInfo] = {}
        self.connections: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.capabilities = ["blocks", "transactions"]
        self.server = None
        self.running = False
        self.sync_in_progress = False
        self.sync_locks: Dict[str, asyncio.Lock] = {}

        # Initialize message handlers
        self.message_handlers = {
            MessageType.HANDSHAKE: self._handle_handshake,
            MessageType.PEER_LIST: self._handle_peer_list,
            MessageType.PING: self._handle_ping,
            MessageType.PONG: self._handle_pong,
            MessageType.NEW_BLOCK: self._handle_new_block,
            MessageType.NEW_TRANSACTION: self._handle_new_transaction,
            MessageType.BLOCK_REQUEST: self._handle_block_request,
            MessageType.BLOCK_RESPONSE: self._handle_block_response,
            MessageType.SYNC_REQUEST: self._handle_sync_request,
            MessageType.SYNC_RESPONSE: self._handle_sync_response
        }

    # Core Network Methods
    async def start(self):
        """Start the P2P node"""
        self.running = True
        
        # Start WebSocket server
        self.server = await websockets.serve(
            self._handle_connection,
            self.host,
            self.port
        )
        
        logger.info(f"P2P Node started on {self.host}:{self.port}")
        
        # Start background tasks
        asyncio.create_task(self._maintain_peers())
        asyncio.create_task(self._discover_peers())
        asyncio.create_task(self._ping_peers())
        asyncio.create_task(self._sync_blockchain())

    async def stop(self):
        """Stop the P2P node"""
        self.running = False
        
        for connection in self.connections.values():
            await connection.close()
        
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        logger.info("P2P Node stopped")

    async def connect_to_peer(self, address: str, port: int):
        """Connect to a new peer"""
        if len(self.peers) >= self.max_peers:
            logger.debug("Maximum peer limit reached")
            return

        try:
            uri = f"ws://{address}:{port}"
            async with websockets.connect(uri) as websocket:
                handshake_msg = Message(
                    type=MessageType.HANDSHAKE,
                    payload={
                        "node_id": self.node_id,
                        "version": self.version,
                        "capabilities": self.capabilities,
                        "current_height": await self.blockchain_state.get_current_height()
                    },
                    sender=self.node_id
                )
                await websocket.send(handshake_msg.serialize())
                
                while self.running:
                    try:
                        message = await websocket.recv()
                        await self._handle_message(Message.deserialize(message), websocket)
                    except ConnectionClosed:
                        break
                    except Exception as e:
                        logger.error(f"Error handling message: {str(e)}")
                        break
                        
        except Exception as e:
            logger.error(f"Failed to connect to peer {address}:{port}: {str(e)}")

    async def _handle_connection(self, websocket: websockets.WebSocketServerProtocol, path: str):
        """Handle incoming WebSocket connection"""
        peer_id = None
        try:
            if len(self.peers) >= self.max_peers:
                await websocket.close()
                return
                
            message = await websocket.recv()
            message = Message.deserialize(message)
            
            if message.type != MessageType.HANDSHAKE:
                await websocket.close()
                return
                
            peer_id = message.payload["node_id"]
            self.connections[peer_id] = websocket
            self.peers[peer_id] = PeerInfo(
                node_id=peer_id,
                address=websocket.remote_address[0],
                port=websocket.remote_address[1],
                last_seen=time.time(),
                version=message.payload["version"],
                capabilities=message.payload["capabilities"],
                last_block_height=message.payload.get("current_height")
            )
            
            response = Message(
                type=MessageType.HANDSHAKE,
                payload={
                    "node_id": self.node_id,
                    "version": self.version,
                    "capabilities": self.capabilities,
                    "current_height": await self.blockchain_state.get_current_height()
                },
                sender=self.node_id
            )
            await websocket.send(response.serialize())
            
            while self.running:
                try:
                    message = await websocket.recv()
                    await self._handle_message(Message.deserialize(message), websocket)
                except ConnectionClosed:
                    break
                except Exception as e:
                    logger.error(f"Error handling message: {str(e)}")
                    break
                    
        except Exception as e:
            logger.error(f"Connection handler error: {str(e)}")
        finally:
            if peer_id:
                if peer_id in self.connections:
                    del self.connections[peer_id]
                if peer_id in self.peers:
                    del self.peers[peer_id]

    async def _handle_message(self, message: Message, websocket: websockets.WebSocketServerProtocol):
        """Route message to appropriate handler"""
        try:
            if message.sender in self.peers:
                self.peers[message.sender].last_seen = time.time()
            
            handler = self.message_handlers.get(message.type)
            if handler:
                await handler(message, websocket)
            else:
                logger.warning(f"Unhandled message type: {message.type}")
                
        except Exception as e:
            logger.error(f"Error in message handler: {str(e)}")

    async def broadcast_message(self, message: Message):
        """Broadcast a message to all connected peers"""
        for connection in self.connections.values():
            try:
                await connection.send(message.serialize())
            except Exception as e:
                logger.error(f"Failed to broadcast message: {str(e)}")

    # Message Type Handlers
    async def _handle_handshake(self, message: Message, websocket: websockets.WebSocketServerProtocol):
        """Handle handshake message"""
        try:
            peer_id = message.payload["node_id"]
            
            if peer_id in self.peers:
                self.peers[peer_id].last_block_height = message.payload.get("current_height")
                
            peer_list_msg = Message(
                type=MessageType.PEER_LIST,
                payload={
                    "peers": [asdict(peer) for peer in self.peers.values()]
                },
                sender=self.node_id
            )
            await websocket.send(peer_list_msg.serialize())
            
        except Exception as e:
            logger.error(f"Error handling handshake: {str(e)}")

    async def _handle_peer_list(self, message: Message, websocket: websockets.WebSocketServerProtocol):
        """Handle peer list message"""
        try:
            for peer_data in message.payload["peers"]:
                peer_id = peer_data["node_id"]
                if peer_id not in self.peers and peer_id != self.node_id:
                    asyncio.create_task(
                        self.connect_to_peer(peer_data["address"], peer_data["port"])
                    )
        except Exception as e:
            logger.error(f"Error handling peer list: {str(e)}")

    async def _handle_ping(self, message: Message, websocket: websockets.WebSocketServerProtocol):
        """Handle ping message"""
        try:
            if message.sender in self.peers and "current_height" in message.payload:
                self.peers[message.sender].last_block_height = message.payload["current_height"]
            
            pong_msg = Message(
                type=MessageType.PONG,
                payload={
                    "current_height": await self.blockchain_state.get_current_height()
                },
                sender=self.node_id
            )
            await websocket.send(pong_msg.serialize())
        
        except Exception as e:
            logger.error(f"Error handling ping: {str(e)}")

    async def _handle_pong(self, message: Message, websocket: websockets.WebSocketServerProtocol):
        """Handle pong message"""
        try:
            if message.sender in self.peers:
                self.peers[message.sender].last_seen = time.time()
                if "current_height" in message.payload:
                    self.peers[message.sender].last_block_height = message.payload["current_height"]
        except Exception as e:
            logger.error(f"Error handling pong: {str(e)}")

    async def _handle_new_block(self, message: Message, websocket: websockets.WebSocketServerProtocol):
        """Handle new block announcement"""
        try:
            block_data = message.payload["block"]
            block = Block.deserialize(block_data)
            
            if not block.is_valid():
                logger.warning(f"Received invalid block from peer {message.sender}")
                return

            if await self.blockchain_state.has_block(block.hash):
                logger.debug(f"Received already known block {block.hash}")
                return

            success = await self.blockchain_state.process_new_block(block)
            
            if success:
                logger.info(f"Successfully processed new block {block.hash}")
                
                # Clean up mempool
                block_tx_hashes = {tx.hash for tx in block.transactions}
                self.mempool.remove_transactions(block_tx_hashes)
                
                if message.sender in self.peers:
                    self.peers[message.sender].last_block_height = block.height
                
                if message.payload.get("propagate", True):
                    await self._propagate_block(block, exclude_peer=message.sender)
            else:
                logger.warning(f"Failed to process block {block.hash}")
                
                current_height = await self.blockchain_state.get_current_height()
                if block.height > current_height + 1:
                    await self._request_missing_blocks(
                        current_height + 1,
                        block.height - 1,
                        websocket
                    )

        except Exception as e:
            logger.error(f"Error processing new block: {str(e)}")

    async def _handle_new_transaction(self, message: Message, websocket: websockets.WebSocketServerProtocol):
        """Handle new transaction announcement"""
        try:
            tx_data = message.payload["transaction"]
            transaction = Transaction.deserialize(tx_data)
            
            if not transaction.is_valid():
                logger.warning(f"Received invalid transaction from peer {message.sender}")
                return

            if (self.mempool.has_transaction(transaction.hash) or 
                await self.blockchain_state.has_transaction(transaction.hash)):
                logger.debug(f"Received already known transaction {transaction.hash}")
                return

            if self.mempool.add_transaction(transaction):
                logger.info(f"Added new transaction {transaction.hash} to mempool")
                
                if message.payload.get("propagate", True):
                    await self._propagate_transaction(transaction, exclude_peer=message.sender)
            else:
                logger.warning(f"Failed to add transaction {transaction.hash} to mempool")

        except Exception as e:
            logger.error(f"Error processing new transaction: {str(e)}")

    async def _handle_block_request(self, message: Message, websocket: websockets.WebSocketServerProtocol):
        """Handle block request"""
        try:
            block_hash = message.payload["block_hash"]
            block = await self.blockchain_state.get_block(block_hash)
            
            if block:
                response = Message(
                    type=MessageType.BLOCK_RESPONSE,
                    payload={
                        "block": block.serialize(),
                        "request_id": message.payload.get("request_id")
                    },
                    sender=self.node_id
                )
                await websocket.send(response.serialize())
            else:
                logger.warning(f"Requested block {block_hash} not found")

        except Exception as e:
            logger.error(f"Error handling block request: {str(e)}")

    async def _handle_block_response(self, message: Message, websocket: websockets.WebSocketServerProtocol):
        """Handle block response"""
        try:
            block_data = message.payload["block"]
            block = Block.deserialize(block_data)
            
            if not await self.blockchain_state.has_block(block.hash):
                success = await self.blockchain_state.process_new_block(block)
                if success:
                    logger.info(f"Successfully processed block {block.hash} from response")
                    
                    # Clean up mempool
                    block_tx_hashes = {tx.hash for tx in block.transactions}
                    self.mempool.remove_transactions(block_tx_hashes)
                else:
                    logger.warning(f"Failed to process block {block.hash} from response")

        except Exception as e:
            logger.error(f"Error handling block response: {str(e)}")

    # Block and Transaction Propagation Methods
    async def _propagate_block(self, block: Block, exclude_peer: str = None):
        """Propagate block to peers"""
        try:
            message = Message(
                type=MessageType.NEW_BLOCK,
                payload={
                    "block": block.serialize(),
                    "propagate": True
                },
                sender=self.node_id
            )
            
            for peer_id, connection in self.connections.items():
                if peer_id != exclude_peer:
                    try:
                        await connection.send(message.serialize())
                    except Exception as e:
                        logger.error(f"Failed to propagate block to peer {peer_id}: {str(e)}")
        
        except Exception as e:
            logger.error(f"Error in block propagation: {str(e)}")

    async def _propagate_transaction(self, transaction: Transaction, exclude_peer: str = None):
        """Propagate transaction to peers"""
        try:
            message = Message(
                type=MessageType.NEW_TRANSACTION,
                payload={
                    "transaction": transaction.serialize(),
                    "propagate": True
                },
                sender=self.node_id
            )
            
            for peer_id, connection in self.connections.items():
                if peer_id != exclude_peer:
                    try:
                        await connection.send(message.serialize())
                    except Exception as e:
                        logger.error(f"Failed to propagate transaction to peer {peer_id}: {str(e)}")
        
        except Exception as e:
            logger.error(f"Error in transaction propagation: {str(e)}")

    async def _handle_sync_request(self, message: Message, websocket: websockets.WebSocketServerProtocol):
        """Handle blockchain sync request"""
        try:
            start_height = message.payload["start_height"]
            end_height = message.payload["end_height"]
            
            # Limit blocks per response for bandwidth management
            max_blocks_per_response = 500
            end_height = min(end_height, start_height + max_blocks_per_response)
            
            # Collect blocks in requested range
            blocks = []
            for height in range(start_height, end_height + 1):
                block = await self.blockchain_state.get_block_by_height(height)
                if block:
                    blocks.append(block.serialize())
            
            response = Message(
                type=MessageType.SYNC_RESPONSE,
                payload={
                    "blocks": blocks,
                    "start_height": start_height,
                    "end_height": end_height,
                    "request_id": message.payload.get("request_id")
                },
                sender=self.node_id
            )
            await websocket.send(response.serialize())

        except Exception as e:
            logger.error(f"Error handling sync request: {str(e)}")

    async def _handle_sync_response(self, message: Message, websocket: websockets.WebSocketServerProtocol):
        """Handle blockchain sync response"""
        try:
            blocks_data = message.payload["blocks"]
            end_height = message.payload["end_height"]
            
            # Process blocks sequentially
            for block_data in blocks_data:
                block = Block.deserialize(block_data)
                if not await self.blockchain_state.has_block(block.hash):
                    success = await self.blockchain_state.process_new_block(block)
                    if not success:
                        logger.warning(f"Failed to process block {block.hash} during sync")
                        break
                    
                    # Clean up mempool
                    block_tx_hashes = {tx.hash for tx in block.transactions}
                    self.mempool.remove_transactions(block_tx_hashes)

            # Update peer's block height
            if message.sender in self.peers:
                self.peers[message.sender].last_block_height = end_height

            # Check if more blocks needed
            if self.sync_in_progress:
                current_height = await self.blockchain_state.get_current_height()
                if current_height < end_height:
                    await self._request_missing_blocks(
                        current_height + 1,
                        end_height,
                        websocket
                    )
                else:
                    self.sync_in_progress = False
                    logger.info("Blockchain sync completed")

        except Exception as e:
            logger.error(f"Error handling sync response: {str(e)}")

    # Background Tasks
    async def _sync_blockchain(self):
        """Periodically check and sync blockchain with peers"""
        while self.running:
            try:
                if not self.sync_in_progress and self.peers:
                    # Find best peer to sync from
                    best_peer = max(
                        self.peers.values(),
                        key=lambda p: p.last_block_height or 0
                    )
                    
                    current_height = await self.blockchain_state.get_current_height()
                    if best_peer.last_block_height > current_height:
                        self.sync_in_progress = True
                        logger.info(f"Starting blockchain sync from height {current_height} to {best_peer.last_block_height}")
                        
                        while current_height < best_peer.last_block_height and self.running:
                            end_height = min(
                                current_height + 500,
                                best_peer.last_block_height
                            )
                            await self._request_missing_blocks(
                                current_height + 1,
                                end_height,
                                self.connections[best_peer.node_id]
                            )
                            current_height = end_height
                            await asyncio.sleep(1)  # Prevent overwhelming the network
                        
                        self.sync_in_progress = False
            
            except Exception as e:
                logger.error(f"Error in blockchain sync: {str(e)}")
                self.sync_in_progress = False
            
            await asyncio.sleep(60)  # Check every minute

    async def _maintain_peers(self):
        """Maintain peer list by removing inactive peers"""
        while self.running:
            try:
                current_time = time.time()
                inactive_peers = [
                    peer_id for peer_id, peer in self.peers.items()
                    if current_time - peer.last_seen > 300  # 5 minutes timeout
                ]
                
                for peer_id in inactive_peers:
                    logger.info(f"Removing inactive peer {peer_id}")
                    if peer_id in self.connections:
                        await self.connections[peer_id].close()
                    del self.peers[peer_id]
                    del self.connections[peer_id]
                
            except Exception as e:
                logger.error(f"Error maintaining peers: {str(e)}")
            
            await asyncio.sleep(60)

    async def _discover_peers(self):
        """Periodic peer discovery"""
        while self.running:
            try:
                if len(self.peers) < self.max_peers and self.peers:
                    random_peer = random.choice(list(self.connections.values()))
                    peer_list_request = Message(
                        type=MessageType.PEER_LIST,
                        payload={},
                        sender=self.node_id
                    )
                    await random_peer.send(peer_list_request.serialize())
                
            except Exception as e:
                logger.error(f"Error in peer discovery: {str(e)}")
            
            await asyncio.sleep(300)

    async def _ping_peers(self):
        """Periodic ping to maintain connections"""
        while self.running:
            try:
                current_height = await self.blockchain_state.get_current_height()
                ping_msg = Message(
                    type=MessageType.PING,
                    payload={
                        "current_height": current_height
                    },
                    sender=self.node_id
                )
                await self.broadcast_message(ping_msg)
            
            except Exception as e:
                logger.error(f"Error pinging peers: {str(e)}")
            
            await asyncio.sleep(60)

    # Utility Methods
    async def _request_missing_blocks(self, start_height: int, end_height: int, websocket: websockets.WebSocketServerProtocol):
        """Request missing blocks from peer"""
        try:
            message = Message(
                type=MessageType.SYNC_REQUEST,
                payload={
                    "start_height": start_height,
                    "end_height": end_height,
                    "request_id": random.getrandbits(32)
                },
                sender=self.node_id
            )
            
            await websocket.send(message.serialize())
            logger.info(f"Requested blocks from height {start_height} to {end_height}")
        
        except Exception as e:
            logger.error(f"Error requesting missing blocks: {str(e)}")

    def _generate_node_id(self) -> str:
        """Generate unique node ID"""
        return f"node_{random.getrandbits(32):08x}"

    # Public Interface Methods
    @property
    def peer_count(self) -> int:
        """Get the current number of connected peers"""
        return len(self.peers)

    @property
    def is_syncing(self) -> bool:
        """Check if the node is currently syncing"""
        return self.sync_in_progress

    def get_peer_info(self, peer_id: str) -> Optional[PeerInfo]:
        """Get information about a specific peer"""
        return self.peers.get(peer_id)

    def get_network_state(self) -> dict:
        """Get current network state information"""
        return {
            "peer_count": self.peer_count,
            "is_syncing": self.is_syncing,
            "connected_peers": [asdict(peer) for peer in self.peers.values()],
            "node_id": self.node_id,
            "version": self.version,
            "capabilities": self.capabilities
        }                        