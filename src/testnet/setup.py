# src/testnet/setup.py
from typing import List, Dict
import os
import json
import argparse
from decimal import Decimal
import sys
from pathlib import Path

# Add parent directory to path so we can import our modules
sys.path.append(str(Path(__file__).parent.parent))

from blockchain.blockchain import Blockchain
from blockchain.block import Block
from network.node import Node
from blockchain.transaction import Transaction
import logging

class TestnetSetup:
    def __init__(self, base_port: int = 5000):
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
        self.logger.info(f"Initializing testnet with {num_nodes} nodes")
        
        # Create config directory
        self.config_dir.mkdir(exist_ok=True)
        
        # Create genesis block and initial blockchain
        blockchain = self._create_genesis_blockchain()
        
        # Initialize nodes
        for i in range(num_nodes):
            node = self._create_node(i, blockchain)
            self.test_nodes.append(node)
            
        # Connect nodes to each other
        self._connect_nodes()
        
        # Save configuration
        self._save_config()
        
        self.logger.info("Testnet initialization complete")

    def _create_genesis_blockchain(self) -> Blockchain:
        """Create blockchain with genesis block"""
        blockchain = Blockchain()
        
        # Create genesis transaction
        genesis_tx = Transaction(
            sender="0",
            recipient="TestnetGenesis",
            amount=Decimal("1000000"),
            transaction_type="genesis"
        )
        
        # Create genesis block
        genesis_block = Block(
            height=0,
            previous_hash="0",
            transactions=[genesis_tx],
            timestamp=0
        )
        
        blockchain.add_block(genesis_block)
        return blockchain

    def _create_node(self, node_index: int, blockchain: Blockchain) -> Node:
        """Create and initialize a testnet node"""
        port = self.base_port + node_index
        node = Node(
            host="127.0.0.1",
            port=port,
            blockchain=blockchain
        )
        
        # Create node directory
        node_dir = self.config_dir / f"node_{node_index}"
        node_dir.mkdir(exist_ok=True)
        
        return node

    def _connect_nodes(self):
        """Connect all nodes to each other"""
        for i, node in enumerate(self.test_nodes):
            for j, peer_node in enumerate(self.test_nodes):
                if i != j:
                    node.connect_to_peer(("127.0.0.1", self.base_port + j))

    def _save_config(self):
        """Save testnet configuration"""
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

    def start_testnet(self):
        """Start all testnet nodes"""
        self.logger.info("Starting testnet nodes")
        for node in self.test_nodes:
            try:
                node.start()
            except Exception as e:
                self.logger.error(f"Failed to start node on port {node.port}: {str(e)}")

    def stop_testnet(self):
        """Stop all testnet nodes"""
        self.logger.info("Stopping testnet nodes")
        for node in self.test_nodes:
            try:
                node.stop()
            except Exception as e:
                self.logger.error(f"Error stopping node on port {node.port}: {str(e)}")

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
        default=5000,
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