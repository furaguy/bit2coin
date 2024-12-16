# File: src/network/consensus_network.py

import asyncio
import json
from typing import Dict, List, Optional, Callable, Any
import websockets
from dataclasses import asdict, dataclass
from ..consensus.consensus_manager import ConsensusManager, Block
from ..consensus.slashing import SlashingEvent

@dataclass
class NetworkMessage:
    type: str
    data: Dict
    sender: str
    signature: str
    timestamp: int

class ConsensusNetwork:
    def __init__(
        self,
        consensus_manager: ConsensusManager,
        node_id: str,
        host: str = "0.0.0.0",
        port: int = 8000
    ):
        self.consensus_manager = consensus_manager
        self.node_id = node_id
        self.host = host
        self.port = port
        self.peers: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.message_handlers: Dict[str, Callable] = {
            "new_block": self._handle_new_block,
            "block_vote": self._handle_block_vote,
            "slashing_event": self._handle_slashing_event,
            "validation_request": self._handle_validation_request,
            "peer_discovery": self._handle_peer_discovery
        }

    async def start(self):
        """Start the network server and connect to initial peers."""
        server = await websockets.serve(
            self._handle_connection,
            self.host,
            self.port
        )
        print(f"Network server started on {self.host}:{self.port}")
        await self._connect_to_initial_peers()
        await server.wait_closed()

    async def _handle_connection(
        self,
        websocket: websockets.WebSocketServerProtocol,
        path: str
    ):
        """Handle incoming peer connections."""
        try:
            # Perform handshake
            handshake = await websocket.recv()
            peer_info = json.loads(handshake)
            peer_id = peer_info["node_id"]

            # Register peer
            self.peers[peer_id] = websocket
            print(f"New peer connected: {peer_id}")

            # Handle messages from this peer
            try:
                async for message in websocket:
                    await self._process_message(json.loads(message), peer_id)
            except websockets.exceptions.ConnectionClosed:
                print(f"Peer disconnected: {peer_id}")
            finally:
                del self.peers[peer_id]
        except Exception as e:
            print(f"Error handling connection: {e}")

    async def _process_message(self, message_data: Dict, peer_id: str):
        """Process incoming network messages."""
        try:
            message = NetworkMessage(**message_data)
            handler = self.message_handlers.get(message.type)
            if handler:
                await handler(message, peer_id)
            else:
                print(f"Unknown message type: {message.type}")
        except Exception as e:
            print(f"Error processing message: {e}")

    async def broadcast_new_block(self, block: Block):
        """Broadcast a new block to all peers."""
        message = NetworkMessage(
            type="new_block",
            data=asdict(block),
            sender=self.node_id,
            signature="",  # TODO: Implement signing
            timestamp=block.timestamp
        )
        await self._broadcast_message(message)

    async def request_validation(self, validator: str, block: Block):
        """Request block validation from a specific validator."""
        message = NetworkMessage(
            type="validation_request",
            data={
                "block": asdict(block),
                "validator": validator
            },
            sender=self.node_id,
            signature="",  # TODO: Implement signing
            timestamp=block.timestamp
        )
        await self._send_to_peer(validator, message)

    async def broadcast_slashing_event(self, event: SlashingEvent):
        """Broadcast a slashing event to all peers."""
        message = NetworkMessage(
            type="slashing_event",
            data=asdict(event),
            sender=self.node_id,
            signature="",  # TODO: Implement signing
            timestamp=event.timestamp
        )
        await self._broadcast_message(message)

    async def submit_vote(
        self,
        block_hash: str,
        block_height: int,
        validator: str,
        signature: str
    ):
        """Submit a validation vote to the network."""
        message = NetworkMessage(
            type="block_vote",
            data={
                "block_hash": block_hash,
                "block_height": block_height,
                "validator": validator,
                "signature": signature
            },
            sender=self.node_id,
            signature="",  # TODO: Implement signing
            timestamp=int(asyncio.get_event_loop().time())
        )
        await self._broadcast_message(message)

    # Message Handlers
    async def _handle_new_block(self, message: NetworkMessage, peer_id: str):
        """Handle receiving a new block."""
        block = Block(**message.data)
        await self.consensus_manager.process_new_block(block)

    async def _handle_block_vote(self, message: NetworkMessage, peer_id: str):
        """Handle receiving a block vote."""
        vote_data = message.data
        await self.consensus_manager.process_vote(
            vote_data["validator"],
            vote_data["block_hash"],
            vote_data["block_height"],
            vote_data["signature"]
        )

    async def _handle_slashing_event(self, message: NetworkMessage, peer_id: str):
        """Handle receiving a slashing event."""
        event = SlashingEvent(**message.data)
        await self.consensus_manager.handle_slashing_event(event)

    async def _handle_validation_request(
        self,
        message: NetworkMessage,
        peer_id: str
    ):
        """Handle receiving a validation request."""
        if self.consensus_manager.validator_selector.is_active_validator(
            self.node_id
        ):
            block = Block(**message.data["block"])
            # TODO: Implement validation logic
            signature = ""  # TODO: Implement signing
            await self.submit_vote(
                block.hash,
                block.height,
                self.node_id,
                signature
            )

    async def _handle_peer_discovery(self, message: NetworkMessage, peer_id: str):
        """Handle peer discovery messages."""
        new_peers = message.data.get("peers", [])
        for peer in new_peers:
            if peer["node_id"] not in self.peers:
                await self._connect_to_peer(peer["host"], peer["port"])

    # Utility Methods
    async def _broadcast_message(self, message: NetworkMessage):
        """Broadcast a message to all connected peers."""
        message_data = json.dumps(asdict(message))
        await asyncio.gather(*[
            peer.send(message_data)
            for peer in self.peers.values()
        ])

    async def _send_to_peer(self, peer_id: str, message: NetworkMessage):
        """Send a message to a specific peer."""
        if peer_id in self.peers:
            await self.peers[peer_id].send(json.dumps(asdict(message)))

    async def _connect_to_peer(self, host: str, port: int):
        """Connect to a new peer."""
        try:
            uri = f"ws://{host}:{port}"
            async with websockets.connect(uri) as websocket:
                # Send handshake
                await websocket.send(json.dumps({
                    "node_id": self.node_id,
                    "host": self.host,
                    "port": self.port
                }))
                # Add to peers
                handshake = await websocket.recv()
                peer_info = json.loads(handshake)
                self.peers[peer_info["node_id"]] = websocket
        except Exception as e:
            print(f"Failed to connect to peer {host}:{port}: {e}")

    async def _connect_to_initial_peers(self):
        """Connect to initial set of peers (bootstrap nodes)."""
        # TODO: Implement peer discovery/bootstrap mechanism
        initial_peers = [
            # Add your bootstrap nodes here
            # {"host": "peer1.example.com", "port": 8000},
            # {"host": "peer2.example.com", "port": 8000},
        ]
        for peer in initial_peers:
            await self._connect_to_peer(peer["host"], peer["port"])