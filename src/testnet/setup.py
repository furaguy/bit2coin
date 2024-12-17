# src/testnet/setup.py
from typing import List, Dict
import os
import json
import argparse
from decimal import Decimal
import sys
import threading
import time
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.blockchain.blockchain import Blockchain
from src.blockchain.block import Block
from src.network.node import Node
from src.blockchain.transaction import Transaction, TransactionType
import logging

class TestnetSetup:
    def __init__(self, base_port: int = 6000):
        self.base_port = base_port
        self.test_nodes: List[Node] = []
        self.config_dir = Path("testnet_data")
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger("testnet-setup")

    def initialize_testnet(self, num_nodes: int = 3):
        """Initialize testnet with specified number of nodes"""
        try:
            self.logger.info(f"Initializing testnet with {num_nodes} nodes")
            
            # Create config directory
            self.config_dir.mkdir(exist_ok=True)
            self.logger.info(f"Created config directory: {self.config_dir}")
            
            # Create genesis block and initial blockchain
            self.logger.info("Creating genesis blockchain")
            blockchain = self._create_genesis_blockchain()
            
            # Initialize nodes
            self.logger.info("Initializing nodes")
            for i in range(num_nodes):
                self.logger.info(f"Creating node {i}")
                node = self._create_node(i, blockchain)
                self.test_nodes.append(node)
                
            # Connect nodes to each other
            self.logger.info("Connecting nodes")
            self._connect_nodes()
            
            # Save configuration
            self.logger.info("Saving configuration")
            self._save_config()
            
            self.logger.info("Testnet initialization complete")
            
        except Exception as e:
            self.logger.error(f"Error initializing testnet: {str(e)}")
            self.logger.exception(e)
            raise

    def start_testnet(self):
        """Start all testnet nodes"""
        self.logger.info("Starting testnet nodes")
        node_threads = []
        
        try:
            # Load configuration
            config_file = self.config_dir / "testnet_config.json"
            self.logger.info(f"Loading configuration from {config_file}")
            
            with open(config_file, 'r') as f:
                config = json.load(f)
                self.logger.info("Configuration loaded successfully")
                self.logger.info(f"Loaded config: {json.dumps(config, indent=2)}")
            
            # Initialize and start nodes
            for i, node_config in enumerate(config['nodes']):
                try:
                    self.logger.info(f"Starting node {i} on {node_config['host']}:{node_config['port']}")
                    
                    # Initialize blockchain
                    blockchain = Blockchain()
                    
                    # Create node
                    node = Node(
                        host=node_config['host'],
                        port=node_config['port'],
                        blockchain=blockchain
                    )
                    self.test_nodes.append(node)
                    
                    # Start node in a new thread
                    thread = threading.Thread(
                        target=node.start,
                        name=f"Node-{i}"
                    )
                    thread.daemon = False
                    node_threads.append(thread)
                    thread.start()
                    
                    self.logger.info(f"Node {i} thread started successfully")
                    
                except Exception as e:
                    self.logger.error(f"Failed to start node {i}: {str(e)}")
                    self.logger.exception(e)
            
            # Keep main thread alive
            self.logger.info("All nodes started, entering main loop")
            while True:
                time.sleep(1)
                self._check_node_status()
                
        except KeyboardInterrupt:
            self.logger.info("Received shutdown signal")
        except Exception as e:
            self.logger.error(f"Error in testnet startup: {str(e)}")
            self.logger.exception(e)
        finally:
            self._cleanup(node_threads)

    def stop_testnet(self):
        """Stop all testnet nodes"""
        self.logger.info("Stopping testnet nodes")
        for i, node in enumerate(self.test_nodes):
            try:
                self.logger.info(f"Stopping node {i}")
                node.stop()
                self.logger.info(f"Node {i} stopped successfully")
            except Exception as e:
                self.logger.error(f"Error stopping node {i}: {str(e)}")
                self.logger.exception(e)

    def _create_genesis_blockchain(self) -> Blockchain:
        """Create blockchain with genesis block"""
        try:
            self.logger.info("Creating genesis blockchain")
            blockchain = Blockchain()
            
            # Create genesis transaction
            genesis_tx = Transaction(
                sender="0",
                recipient="TestnetGenesis",
                amount=Decimal("1000000"),
                transaction_type=TransactionType.GENESIS
            )
            
            # Create genesis block
            genesis_block = Block(
                height=0,
                previous_hash="0",
                transactions=[genesis_tx],
                timestamp=0
            )
            
            blockchain.add_block(genesis_block)
            self.logger.info("Genesis blockchain created successfully")
            return blockchain
            
        except Exception as e:
            self.logger.error("Failed to create genesis blockchain")
            self.logger.exception(e)
            raise

    def _create_node(self, node_index: int, blockchain: Blockchain) -> Node:
        """Create and initialize a testnet node"""
        try:
            port = self.base_port + node_index
            self.logger.info(f"Creating node {node_index} on port {port}")
            
            node = Node(
                host="127.0.0.1",
                port=port,
                blockchain=blockchain
            )
            
            # Create node directory
            node_dir = self.config_dir / f"node_{node_index}"
            node_dir.mkdir(exist_ok=True)
            self.logger.info(f"Created node directory: {node_dir}")
            
            return node
            
        except Exception as e:
            self.logger.error(f"Failed to create node {node_index}")
            self.logger.exception(e)
            raise

    def _connect_nodes(self):
        """Connect all nodes to each other"""
        try:
            self.logger.info("Connecting nodes to each other")
            for i, node in enumerate(self.test_nodes):
                for j, peer_node in enumerate(self.test_nodes):
                    if i != j:
                        self.logger.info(f"Connecting node {i} to node {j}")
                        node.connect_to_peer(("127.0.0.1", self.base_port + j))
        except Exception as e:
            self.logger.error("Failed to connect nodes")
            self.logger.exception(e)
            raise

    def _save_config(self):
        """Save testnet configuration"""
        try:
            self.logger.info("Saving testnet configuration")
            config = {
                "nodes": [
                    {
                        "id": i,
                        "host": "127.0.0.1",
                        "port": self.base_port + i
                    }
                    for i in range(len(self.test_nodes))
                ],
                "genesis_block": self.test_nodes[0].blockchain.chain[0].to_dict()
            }
            
            config_file = self.config_dir / "testnet_config.json"
            with open(config_file, "w") as f:
                json.dump(config, f, indent=2)
                
            self.logger.info(f"Configuration saved to {config_file}")
            
        except Exception as e:
            self.logger.error("Failed to save configuration")
            self.logger.exception(e)
            raise

    def _check_node_status(self):
        """Check status of all nodes"""
        for i, node in enumerate(self.test_nodes):
            try:
                status = node.get_node_status()
                self.logger.debug(f"Node {i} status: {status}")
            except Exception as e:
                self.logger.error(f"Error checking node {i} status: {str(e)}")

    def _cleanup(self, node_threads: List[threading.Thread]):
        """Clean up resources"""
        self.logger.info("Cleaning up resources")
        try:
            # Stop all nodes
            for i, node in enumerate(self.test_nodes):
                try:
                    self.logger.info(f"Stopping node {i}")
                    node.stop()
                except Exception as e:
                    self.logger.error(f"Error stopping node {i}: {str(e)}")
            
            # Wait for threads to finish
            for thread in node_threads:
                thread.join(timeout=5)
                
            self.logger.info("Cleanup completed")
            
        except Exception as e:
            self.logger.error("Error during cleanup")
            self.logger.exception(e)

def main():
    parser = argparse.ArgumentParser(description="Bit2Coin Testnet Setup")
    parser.add_argument(
        "--nodes", 
        type=int, 
        default=3,
        help="Number of testnet nodes to create"
    )
    parser.add_argument(
        "--base-port", 
        type=int, 
        default=6000,
        help="Base port number for nodes"
    )
    parser.add_argument(
        "--action",
        choices=["init", "start", "stop"],
        required=True,
        help="Action to perform"
    )
    
    args = parser.parse_args()
    
    testnet = TestnetSetup(base_port=args.base_port)
    
    if args.action == "init":
        testnet.initialize_testnet(args.nodes)
    elif args.action == "start":
        if not (Path("testnet_data") / "testnet_config.json").exists():
            print("Testnet not initialized. Run with --action init first")
            return
        testnet.start_testnet()
    elif args.action == "stop":
        testnet.stop_testnet()

if __name__ == "__main__":
    main()