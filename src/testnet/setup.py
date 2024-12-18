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
from src.blockchain.transaction import Transaction, TransactionType, TransactionData
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
                node_blockchain = Blockchain()
                node_blockchain.chain = blockchain.chain.copy()
                node = self._create_node(i, node_blockchain)
                self.test_nodes.append(node)
                
            # Initialize all nodes first (without starting threads)
            self.logger.info("Starting nodes in initialization mode")
            for i, node in enumerate(self.test_nodes):
                try:
                    self.logger.info(f"Starting node {i} on port {node.port}")
                    node.start(init_only=True)
                    time.sleep(1)
                except Exception as e:
                    self.logger.error(f"Failed to start node {i}: {str(e)}")
                    raise

            # Connect nodes
            self.logger.info("Connecting nodes")
            self._connect_nodes()
            
            # Save configuration
            self.logger.info("Saving configuration")
            self._save_config()
            
            # Clean shutdown of initialization nodes
            self.logger.info("Cleaning up initialization nodes")
            for node in self.test_nodes:
                node.stop()
            
            self.test_nodes = []  # Clear nodes after initialization
            self.logger.info("Testnet initialization complete")
            
        except Exception as e:
            self.logger.error(f"Error initializing testnet: {str(e)}")
            self.stop_testnet()  # Clean up on failure
            raise

    def start_testnet(self):
        """Start all testnet nodes"""
        try:
            self.logger.info("Starting testnet nodes")
            
            # Load configuration
            config_file = self.config_dir / "testnet_config.json"
            if not config_file.exists():
                self.logger.error("Configuration file not found. Run initialization first.")
                return
                
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # Create and start nodes
            node_threads = []
            for node_config in config['nodes']:
                try:
                    # Create blockchain instance for each node
                    blockchain = Blockchain()
                    
                    # Create node
                    node = Node(
                        host=node_config['host'],
                        port=node_config['port'],
                        blockchain=blockchain
                    )
                    self.test_nodes.append(node)
                    
                    # Start node in a separate thread
                    self.logger.info(f"Starting node {node_config['id']} on port {node_config['port']}")
                    thread = threading.Thread(
                        target=self._run_node,
                        args=(node,),
                        name=f"Node-{node_config['port']}"
                    )
                    thread.daemon = False
                    node_threads.append(thread)
                    thread.start()
                    
                    # Give each node time to start
                    time.sleep(1)
                    
                except Exception as e:
                    self.logger.error(f"Failed to start node {node_config['id']}: {str(e)}")
                    raise

            self.logger.info("All nodes started, waiting for connections...")
            
            # Wait for nodes to establish connections
            time.sleep(2)
            
            # Enter main loop
            try:
                while True:
                    self._check_node_status()
                    time.sleep(5)
            except KeyboardInterrupt:
                self.logger.info("Received shutdown signal")
            finally:
                self._cleanup(node_threads)
                
        except Exception as e:
            self.logger.error(f"Error starting testnet: {str(e)}")
            raise

    def stop_testnet(self):
        """Stop all testnet nodes"""
        self.logger.info("Stopping testnet nodes")
        for i, node in enumerate(self.test_nodes):
            try:
                self.logger.info(f"Stopping node {i}")
                node.stop()
                self.logger.info(f"Node {i} stopped")
            except Exception as e:
                self.logger.error(f"Error stopping node {i}: {str(e)}")

    def _create_genesis_blockchain(self) -> Blockchain:
        """Create blockchain with genesis block"""
        blockchain = Blockchain()
        
        # Set fixed timestamp for deterministic genesis block
        genesis_timestamp = int(time.time())

        # Create genesis transaction
        genesis_tx = Transaction(
            sender="0",
            recipient="GenesisAddress",
            amount=Decimal("1000000"),
            transaction_type=TransactionType.GENESIS,
            timestamp=genesis_timestamp,
            message="Bit2Coin Genesis Block",
            data={
                "type": TransactionType.GENESIS,
                "validator_address": None,
                "delegation_amount": None,
                "reward_share": None,
                "unbonding_time": None,
                "genesis_message": "Bit2Coin Genesis Block"
            }
        )
        
        # Create genesis block with fixed values
        genesis_block = Block(
            height=0,
            previous_hash="0",
            transactions=[genesis_tx],
            timestamp=genesis_timestamp,
            validator=None,
            version=1
        )
        
        blockchain.add_block(genesis_block)
        self.logger.info(f"Created genesis block with hash: {genesis_block.hash}")
        return blockchain

    def _create_node(self, node_index: int, blockchain: Blockchain) -> Node:
        """Create and initialize a testnet node"""
        port = self.base_port + node_index
        self.logger.info(f"Creating node on port {port}")
        
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

    def _connect_nodes(self):
        """Connect all nodes to each other"""
        self.logger.info("Connecting nodes to each other")
        # Give nodes some time to be ready for connections
        time.sleep(1)
        
        for i, node in enumerate(self.test_nodes):
            for j, peer_node in enumerate(self.test_nodes):
                if i != j:
                    max_attempts = 3
                    for attempt in range(max_attempts):
                        try:
                            success = node.connect_to_peer(("127.0.0.1", self.base_port + j))
                            if success:
                                self.logger.info(f"Connected node {i} to node {j}")
                                break
                            else:
                                self.logger.warning(
                                    f"Failed to connect node {i} to node {j} "
                                    f"(attempt {attempt + 1}/{max_attempts})"
                                )
                        except Exception as e:
                            self.logger.error(
                                f"Error connecting nodes {i} and {j} "
                                f"(attempt {attempt + 1}/{max_attempts}): {str(e)}"
                            )
                        if attempt < max_attempts - 1:
                            time.sleep(1)  # Wait before retry

    def _run_node(self, node: Node):
        """Run a single node"""
        try:
            node.start(init_only=False)  # Start in full mode
            while node.is_healthy():
                time.sleep(1)
        except Exception as e:
            self.logger.error(f"Error running node on port {node.port}: {str(e)}")
        finally:
            node.stop()

    def _check_node_status(self):
        """Check status of all nodes"""
        for node in self.test_nodes:
            try:
                status = node.get_node_status()
                self.logger.info(f"Node {node.port} status: {status}")
            except Exception as e:
                self.logger.error(f"Error checking node {node.port} status: {str(e)}")

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

    def _cleanup(self, node_threads: List[threading.Thread]):
        """Clean up resources"""
        self.logger.info("Cleaning up resources")
        try:
            # Stop all nodes
            for node in self.test_nodes:
                try:
                    self.logger.info(f"Stopping node on port {node.port}")
                    node.stop()
                except Exception as e:
                    self.logger.error(f"Error stopping node on port {node.port}: {str(e)}")
            
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