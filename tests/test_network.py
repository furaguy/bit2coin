# tests/test_network.py
import pytest
import socket
import json
import time
from unittest.mock import Mock, patch
from src.network.peer_discovery import PeerDiscovery
from src.network.node import Node
from src.blockchain.blockchain import Blockchain
from src.blockchain.block import Block
from src.blockchain.transaction import Transaction

class TestNetwork:
    @pytest.fixture
    def peer_discovery(self):
        return PeerDiscovery("127.0.0.1", 5000)

    @pytest.fixture
    def node(self):
        return Node("127.0.0.1", 5000, Blockchain())

    @patch('socket.socket')
    def test_peer_discovery(self, mock_socket):
        # Configure mock socket
        mock_socket.return_value.recvfrom.side_effect = socket.timeout()
        
        # Create PeerDiscovery instance with mocked socket
        discovery = PeerDiscovery("127.0.0.1", 5000)
        discovery.broadcast_socket = mock_socket.return_value
        
        try:
            # Start discovery
            discovery.start()
            
            # Force a broadcast
            discovery._broadcast_presence()
            
            # Wait briefly for the broadcast to happen
            time.sleep(0.2)
            
            # Verify that sendto was called
            assert mock_socket.return_value.sendto.called
            
            # Verify the message format
            args = mock_socket.return_value.sendto.call_args[0]
            message = json.loads(args[0].decode())
            assert "node_id" in message
            assert "timestamp" in message
            assert message["node_id"] == "127.0.0.1:5000"
            
        finally:
            # Clean up
            discovery.stop()

    def test_node_connection(self, node):
        peer_address = ("127.0.0.1", 5001)
        assert node.connect_to_peer(peer_address) == True
        assert len(node.peers) == 1

    @patch('socket.socket')
    def test_block_propagation(self, mock_socket, node):
        mock_peer = Mock()
        node.peers = [("127.0.0.1", 5001)]
        
        new_block = Block(
            index=1,
            transactions=[],
            previous_hash="0" * 64,
            timestamp=int(time.time())
        )
        
        # Configure mock socket
        mock_socket.return_value.connect.return_value = None
        
        # Broadcast block
        node.broadcast_block(new_block)
        
        # Verify socket operations
        assert mock_socket.return_value.connect.called
        assert mock_socket.return_value.send.called

    @patch('socket.socket')
    def test_transaction_propagation(self, mock_socket, node):
        mock_peer = Mock()
        node.peers = [("127.0.0.1", 5001)]
        
        tx = Transaction(
            sender="sender_address",
            recipient="recipient_address",
            amount=10.0,
            timestamp=int(time.time())
        )
        
        # Configure mock socket
        mock_socket.return_value.connect.return_value = None
        
        # Broadcast transaction
        node.broadcast_transaction(tx)
        
        # Verify socket operations
        assert mock_socket.return_value.connect.called
        assert mock_socket.return_value.send.called

    def test_peer_synchronization(self, node):
        peer_blockchain = Blockchain()
        peer_node = Node("127.0.0.1", 5001, peer_blockchain)
        
        # Add some blocks to peer blockchain
        new_block = Block(
            index=1,
            transactions=[],
            previous_hash=peer_blockchain.chain[-1].hash,
            timestamp=int(time.time())
        )
        peer_blockchain.add_block(new_block)
        
        # Test synchronization
        assert node.synchronize_with_peer(peer_node) == True
        assert len(node.blockchain.chain) == len(peer_blockchain.chain)