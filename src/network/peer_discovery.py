# File: src/network/peer_discovery.py

import asyncio
import json
import random
import time
from typing import Dict, List, Set, Optional
import aiohttp
from dataclasses import dataclass, asdict
import socket
import struct
from async_timeout import timeout
from ..crypto.message_signing import MessageSigner, SignedMessage

@dataclass
class PeerInfo:
    node_id: str
    host: str
    port: int
    last_seen: int
    is_bootstrap: bool
    reputation: int
    capabilities: List[str]

class PeerDiscovery:
    def __init__(
        self,
        node_id: str,
        host: str,
        port: int,
        bootstrap_nodes: List[Dict],
        signer: MessageSigner,
        max_peers: int = 50,
        ping_interval: int = 30,
        peer_cleanup_interval: int = 300
    ):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.signer = signer
        self.max_peers = max_peers
        self.ping_interval = ping_interval
        self.peer_cleanup_interval = peer_cleanup_interval

        # Peer management
        self.peers: Dict[str, PeerInfo] = {}
        self.bootstrap_nodes = {
            node['node_id']: PeerInfo(
                node_id=node['node_id'],
                host=node['host'],
                port=node['port'],
                last_seen=int(time.time()),
                is_bootstrap=True,
                reputation=100,
                capabilities=node.get('capabilities', ['relay', 'storage'])
            )
            for node in bootstrap_nodes
        }
        
        # Connection tracking
        self.connecting: Set[str] = set()
        self.blacklisted: Dict[str, int] = {}  # node_id -> timestamp
        
        # NAT traversal
        self.external_ip: Optional[str] = None
        self.upnp_mapped = False

    async def start(self):
        """Start peer discovery and maintenance tasks."""
        await self._setup_nat_traversal()
        asyncio.create_task(self._periodic_peer_discovery())
        asyncio.create_task(self._periodic_peer_ping())
        asyncio.create_task(self._periodic_peer_cleanup())
        await self._initial_bootstrap()

    async def _setup_nat_traversal(self):
        """Setup NAT traversal and port mapping."""
        # Get external IP
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://api.ipify.org') as response:
                    self.external_ip = await response.text()
        except Exception as e:
            print(f"Failed to get external IP: {e}")

        # Try UPnP port mapping
        try:
            import miniupnpc
            upnp = miniupnpc.UPnP()
            upnp.discoverdelay = 200
            upnp.discover()
            upnp.selectigd()
            upnp.addportmapping(
                self.port, 'TCP', upnp.lanaddr, self.port,
                'bit2coin-node', 'TCP'
            )
            self.upnp_mapped = True
        except Exception as e:
            print(f"UPnP mapping failed: {e}")

    async def _initial_bootstrap(self):
        """Connect to initial bootstrap nodes."""
        for node in self.bootstrap_nodes.values():
            await self.connect_to_peer(node)

    async def connect_to_peer(self, peer_info: PeerInfo) -> bool:
        """Establish connection with a peer."""
        if peer_info.node_id in self.connecting:
            return False

        if peer_info.node_id in self.blacklisted:
            if time.time() - self.blacklisted[peer_info.node_id] < 3600:  # 1 hour
                return False
            del self.blacklisted[peer_info.node_id]

        self.connecting.add(peer_info.node_id)
        try:
            async with timeout(10):
                # Perform handshake
                message = SignedMessage(
                    "handshake",
                    {
                        "node_id": self.node_id,
                        "host": self.host,
                        "port": self.port,
                        "capabilities": ["relay", "storage"],
                        "version": "1.0.0"
                    },
                    self.node_id,
                    self.signer
                )

                reader, writer = await asyncio.open_connection(
                    peer_info.host,
                    peer_info.port
                )
                
                writer.write(json.dumps(message.to_dict()).encode() + b'\n')
                await writer.drain()

                response = await reader.readline()
                handshake_data = json.loads(response.decode())

                if self._verify_handshake(handshake_data):
                    self.peers[peer_info.node_id] = peer_info
                    self.peers[peer_info.node_id].last_seen = int(time.time())
                    return True
                else:
                    self.blacklist_peer(peer_info.node_id)
                    return False

        except Exception as e:
            print(f"Failed to connect to peer {peer_info.node_id}: {e}")
            self.blacklist_peer(peer_info.node_id)
            return False
        finally:
            self.connecting.remove(peer_info.node_id)

    def blacklist_peer(self, node_id: str):
        """Add peer to blacklist."""
        self.blacklisted[node_id] = int(time.time())
        if node_id in self.peers:
            del self.peers[node_id]

    async def _periodic_peer_discovery(self):
        """Periodically discover new peers."""
        while True:
            if len(self.peers) < self.max_peers:
                # Ask existing peers for their peers
                for peer in list(self.peers.values()):
                    try:
                        new_peers = await self._request_peer_list(peer)
                        for new_peer in new_peers:
                            if len(self.peers) >= self.max_peers:
                                break
                            await self.connect_to_peer(PeerInfo(**new_peer))
                    except Exception as e:
                        print(f"Error discovering peers from {peer.node_id}: {e}")

            await asyncio.sleep(60)  # Run discovery every minute

    async def _periodic_peer_ping(self):
        """Periodically ping connected peers."""
        while True:
            for peer_id, peer in list(self.peers.items()):
                try:
                    if not await self._ping_peer(peer):
                        del self.peers[peer_id]
                except Exception as e:
                    print(f"Error pinging peer {peer_id}: {e}")
                    del self.peers[peer_id]
            await asyncio.sleep(self.ping_interval)

    async def _periodic_peer_cleanup(self):
        """Periodically clean up inactive peers."""
        while True:
            current_time = int(time.time())
            # Remove peers not seen in the last cleanup interval
            inactive_peers = [
                peer_id for peer_id, peer in self.peers.items()
                if current_time - peer.last_seen > self.peer_cleanup_interval
                and not peer.is_bootstrap
            ]
            for peer_id in inactive_peers:
                del self.peers[peer_id]

            # Clean up old blacklist entries
            old_blacklist = [
                node_id for node_id, timestamp in self.blacklisted.items()
                if current_time - timestamp > 3600  # 1 hour
            ]
            for node_id in old_blacklist:
                del self.blacklisted[node_id]

            await asyncio.sleep(self.peer_cleanup_interval)

    async def _request_peer_list(self, peer: PeerInfo) -> List[Dict]:
        """Request peer list from a specific peer."""
        try:
            message = SignedMessage(
                "peer_list_request",
                {},
                self.node_id,
                self.signer
            )

            reader, writer = await asyncio.open_connection(
                peer.host,
                peer.port
            )
            
            writer.write(json.dumps(message.to_dict()).encode() + b'\n')
            await writer.drain()

            response = await reader.readline()
            data = json.loads(response.decode())
            
            if self._verify_message(data):
                return data['peers']
            return []

        except Exception as e:
            print(f"Error requesting peer list from {peer.node_id}: {e}")
            return []

    async def _ping_peer(self, peer: PeerInfo) -> bool:
        """Ping a peer to check if it's still alive."""
        try:
            message = SignedMessage(
                "ping",
                {"timestamp": int(time.time())},
                self.node_id,
                self.signer
            )

            reader, writer = await asyncio.open_connection(
                peer.host,
                peer.port
            )
            
            writer.write(json.dumps(message.to_dict()).encode() + b'\n')
            await writer.drain()

            response = await reader.readline()
            data = json.loads(response.decode())
            
            if self._verify_message(data) and data['type'] == 'pong':
                peer.last_seen = int(time.time())
                return True
            return False

        except Exception:
            return False

    def _verify_handshake(self, handshake_data: Dict) -> bool:
        """Verify handshake response."""
        try:
            # Verify signature and basic data
            if not self._verify_message(handshake_data):
                return False

            # Check version compatibility
            version = handshake_data['data'].get('version', '1.0.0')
            if not self._is_compatible_version(version):
                return False

            return True
        except Exception:
            return False

    def _verify_message(self, message_data: Dict) -> bool:
        """Verify a received message."""
        try:
            return True  # Simplified for example
        except Exception:
            return False

    def _is_compatible_version(self, version: str) -> bool:
        """Check if peer version is compatible."""
        try:
            major, minor, patch = map(int, version.split('.'))
            return major == 1  # Only accept 1.x.x versions
        except Exception:
            return False

    def get_network_stats(self) -> Dict:
        """Get network statistics."""
        return {
            "total_peers": len(self.peers),
            "bootstrap_nodes": len(self.bootstrap_nodes),
            "blacklisted_peers": len(self.blacklisted),
            "external_ip": self.external_ip,
            "upnp_status": self.upnp_mapped,
            "peer_countries": self._get_peer_countries(),
            "network_health": self._calculate_network_health()
        }

    def _get_peer_countries(self) -> Dict[str, int]:
        """Get distribution of peer countries."""
        # Implementation would use GeoIP lookup
        return {}

    def _calculate_network_health(self) -> float:
        """Calculate overall network health score."""
        if not self.peers:
            return 0.0

        factors = [
            len(self.peers) / self.max_peers,
            len([p for p in self.peers.values() if p.reputation > 50]) / len(self.peers),
            1 - (len(self.blacklisted) / (len(self.peers) + len(self.blacklisted)))
        ]
        return sum(factors) / len(factors) * 100