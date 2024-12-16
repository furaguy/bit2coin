# File: tests/network/test_peer_discovery.py

import pytest
import asyncio
import time
from unittest.mock import MagicMock, patch
from src.network.peer_discovery import PeerDiscovery, PeerInfo
from src.crypto.message_signing import KeyPair, MessageSigner

@pytest.fixture
def message_signer():
    key_pair = KeyPair()
    return MessageSigner(key_pair)

@pytest.fixture
def bootstrap_nodes():
    return [
        {
            "node_id": "bootstrap1",
            "host": "boot1.example.com",
            "port": 8000,
            "capabilities": ["relay", "storage"]
        },
        {
            "node_id": "bootstrap2",
            "host": "boot2.example.com",
            "port": 8000,
            "capabilities": ["relay"]
        }
    ]

@pytest.fixture
def peer_discovery(message_signer, bootstrap_nodes):
    return PeerDiscovery(
        node_id="test_node",
        host="localhost",
        port=8000,
        bootstrap_nodes=bootstrap_nodes,
        signer=message_signer
    )

@pytest.mark.asyncio
async def test_initial_bootstrap(peer_discovery):
    # Mock connect_to_peer
    peer_discovery.connect_to_peer = MagicMock(return_value=True)
    
    await peer_discovery._initial_bootstrap()
    
    assert peer_discovery.connect_to_peer.call_count == 2
    assert len(peer_discovery.bootstrap_nodes) == 2

@pytest.mark.asyncio
async def test_connect_to_peer(peer_discovery):
    peer_info = PeerInfo(
        node_id="test_peer",
        host="localhost",
        port=8001,
        last_seen=int(time.time()),
        is_bootstrap=False,
        reputation=100,
        capabilities=["relay"]
    )
    
    # Mock network connection
    with patch('asyncio.open_connection') as mock_connect:
        mock_reader = MagicMock()
        mock_writer = MagicMock()
        mock_connect.return_value = (mock_reader, mock_writer)
        
        # Mock handshake response
        mock_reader.readline.return_value = asyncio.Future()
        mock_reader.readline.return_value.set_result(
            b'{"type":"handshake","data":{"version":"1.0.0"}}\n'
        )
        
        success = await peer_discovery.connect_to_peer(peer_info)
        assert success
        assert "test_peer" in peer_discovery.peers

@pytest.mark.asyncio
async def test_peer_cleanup(peer_discovery):
    # Add some test peers
    current_time = int(time.time())
    peer_discovery.peers = {
        "active": PeerInfo(
            node_id="active",
            host="localhost",
            port=8001,
            last_seen=current_time,
            is_bootstrap=False,
            reputation=100,
            capabilities=["relay"]
        ),
        "inactive": PeerInfo(
            node_id="inactive",
            host="localhost",
            port=8002,
            last_seen=current_time - 1000,
            is_bootstrap=False,
            reputation=100,
            capabilities=["relay"]
        )
    }
    
    await peer_discovery._periodic_peer_cleanup()
    assert "active" in peer_discovery.peers
    assert "inactive" not in peer_discovery.peers

@pytest.mark.asyncio
async def test_blacklist_mechanism(peer_discovery):
    peer_id = "malicious_peer"
    
    # Test blacklisting
    peer_discovery.blacklist_peer(peer_id)
    assert peer_id in peer_discovery.blacklisted
    
    # Test connection rejection for blacklisted peer
    peer_info = PeerInfo(
        node_id=peer_id,
        host="localhost",
        port=8001,
        last_seen=int(time.time()),
        is_bootstrap=False,
        reputation=100,
        capabilities=["relay"]
    )
    
    success = await peer_discovery.connect_to_peer(peer_info)
    assert not success
    
    # Test blacklist cleanup
    peer_discovery.blacklisted[peer_id] = int(time.time()) - 4000  # Old entry
    await peer_discovery._periodic_peer_cleanup()
    assert peer_id not in peer_discovery.blacklisted

@pytest.mark.asyncio
async def test_network_health_calculation(peer_discovery):
    # Add mix of healthy and unhealthy peers
    peer_discovery.peers = {
        "good1": PeerInfo(
            node_id="good1",
            host="localhost",
            port=8001,
            last_seen=int(time.time()),
            is_bootstrap=False,
            reputation=90,
            capabilities=["relay"]
        ),
        "good2": PeerInfo(
            node_id="good2",
            host="localhost",
            port=8002,
            last_seen=int(time.time()),
            is_bootstrap=False,
            reputation=85,
            capabilities=["relay"]
        ),
        "bad1": PeerInfo(
            node_id="bad1",
            host="localhost",
            port=8003,
            last_seen=int(time.time()),
            is_bootstrap=False,
            reputation=30,
            capabilities=["relay"]
        )
    }
    
    health_score = peer_discovery._calculate_network_health()
    assert 60 <= health_score <= 80  # Expected range for given peer mix

@pytest.mark.asyncio
async def test_peer_discovery_process(peer_discovery):
    # Mock peer list request
    async def mock_request_peer_list(peer):
        return [
            {
                "node_id": "new_peer1",
                "host": "localhost",
                "port": 8001,
                "last_seen": int(time.time()),
                "is_bootstrap": False,
                "reputation": 100,
                "capabilities": ["relay"]
            }
        ]
    
    peer_discovery._request_peer_list = mock_request_peer_list
    peer_discovery.connect_to_peer = MagicMock(return_value=True)
    
    # Add initial peer
    peer_discovery.peers = {
        "existing_peer": PeerInfo(
            node_id="existing_peer",
            host="localhost",
            port=8000,
            last_seen=int(time.time()),
            is_bootstrap=False,
            reputation=100,
            capabilities=["relay"]
        )
    }
    
    # Run discovery
    await peer_discovery._periodic_peer_discovery()
    
    # Verify new peer connection attempt
    peer_discovery.connect_to_peer.assert_called_once()

@pytest.mark.asyncio
async def test_nat_traversal_setup(peer_discovery):
    with patch('aiohttp.ClientSession.get') as mock_get:
        # Mock external IP request
        mock_response = MagicMock()
        mock_response.text = asyncio.Future()
        mock_response.text.set_result('1.2.3.4')
        mock_get.return_value.__aenter__.return_value = mock_response
        
        await peer_discovery._setup_nat_traversal()
        assert peer_discovery.external_ip == '1.2.3.4'

@pytest.mark.asyncio
async def test_peer_ping_mechanism(peer_discovery):
    peer_id = "test_peer"
    peer_info = PeerInfo(
        node_id=peer_id,
        host="localhost",
        port=8001,
        last_seen=int(time.time()) - 100,
        is_bootstrap=False,
        reputation=100,
        capabilities=["relay"]
    )
    peer_discovery.peers[peer_id] = peer_info
    
    # Mock successful ping
    async def mock_ping_peer(peer):
        peer.last_seen = int(time.time())
        return True
    
    peer_discovery._ping_peer = mock_ping_peer
    await peer_discovery._periodic_peer_ping()
    assert peer_id in peer_discovery.peers
    
    # Mock failed ping
    async def mock_failed_ping(peer):
        return False
    
    peer_discovery._ping_peer = mock_failed_ping
    await peer_discovery._periodic_peer_ping()
    assert peer_id not in peer_discovery.peers

@pytest.mark.asyncio
async def test_version_compatibility(peer_discovery):
    assert peer_discovery._is_compatible_version("1.0.0")
    assert peer_discovery._is_compatible_version("1.1.0")
    assert not peer_discovery._is_compatible_version("2.0.0")
    assert not peer_discovery._is_compatible_version("invalid")

@pytest.mark.asyncio
async def test_network_stats(peer_discovery):
    # Add some test peers
    peer_discovery.peers = {
        "peer1": PeerInfo(
            node_id="peer1",
            host="localhost",
            port=8001,
            last_seen=int(time.time()),
            is_bootstrap=False,
            reputation=90,
            capabilities=["relay"]
        ),
        "peer2": PeerInfo(
            node_id="peer2",
            host="localhost",
            port=8002,
            last_seen=int(time.time()),
            is_bootstrap=False,
            reputation=85,
            capabilities=["relay"]
        )
    }
    
    stats = peer_discovery.get_network_stats()
    assert stats["total_peers"] == 2
    assert "network_health" in stats
    assert "external_ip" in stats
    assert "upnp_status" in stats