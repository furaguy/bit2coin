# src/testnet/setup.py
import os
import asyncio
import json
import logging
from typing import List, Dict, Optional
from pathlib import Path
import sys
import argparse
from decimal import Decimal
import time
import shutil
import aiofiles
import signal

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from src.blockchain.blockchain import Blockchain, BlockchainError
from src.blockchain.block import Block
from src.blockchain.transaction import Transaction, TransactionType
from src.wallet.wallet import Wallet
from src.network.node import Node

class TestnetSetup:
    def __init__(self, base_port: int = 6000):
        self.base_port = base_port
        self.test_nodes: List[Node] = []
        self.config_dir = Path("testnet_data")
        self.running = False
        self.blockchain: Optional[Blockchain] = None
        self.shutdown_event = asyncio.Event()
        self.node_wallets = []

        # Setup detailed logging
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('testnet_setup.log')
            ]
        )
        self.logger = logging.getLogger("testnet-setup")

        # Initialize wallets
        self.genesis_wallet = None
        self.test_wallets = []

    def _create_genesis_blockchain(self) -> Blockchain:
        """Create blockchain with genesis block and genesis wallets"""
        try:
            blockchain = Blockchain()
            
            # Create a genesis wallet with substantial funds
            self.genesis_wallet = Wallet.generate_new()
            self.logger.info(f"Created genesis wallet with address: {self.genesis_wallet.address}")
            
            # Create genesis transaction
            genesis_tx = Transaction.create_genesis(
                recipient=self.genesis_wallet.address,
                amount=Decimal('10000000.0'),  # 10 million units
                message="Genesis Block"
            )
            
            # Create genesis block
            genesis_block = Block(
                height=0,
                previous_hash="0",
                transactions=[genesis_tx],
                timestamp=0,
                validator=self.genesis_wallet.address
            )
            
            blockchain.add_block(genesis_block)
            self.logger.debug(f"Genesis block created with hash: {genesis_block.hash}")
            return blockchain
            
        except Exception as e:
            self.logger.error(f"Error creating genesis blockchain: {str(e)}")
            raise BlockchainError(f"Genesis blockchain creation failed: {str(e)}")

    async def _save_blockchain_state(self):
        """Save blockchain state to file"""
        try:
            state = self.blockchain.export_state()
            
            # Create config directory if it doesn't exist
            self.config_dir.mkdir(exist_ok=True)
            
            # Save state to file
            state_file = self.config_dir / "blockchain_state.json"
            async with aiofiles.open(state_file, "w") as f:
                await f.write(json.dumps(state, indent=2))
                
            self.logger.debug("Blockchain state saved successfully")
            
        except Exception as e:
            self.logger.error(f"Error saving blockchain state: {str(e)}")
            raise BlockchainError(f"State save failed: {str(e)}")

    async def _load_blockchain_state(self) -> Blockchain:
        """Load blockchain state from file"""
        try:
            state_file = self.config_dir / "blockchain_state.json"
            if not state_file.exists():
                self.logger.warning("No blockchain state found, creating new blockchain")
                return self._create_genesis_blockchain()
                
            self.logger.debug(f"Loading blockchain state from {state_file}")
            async with aiofiles.open(state_file, "r") as f:
                content = await f.read()
                state = json.loads(content)
                
            blockchain = Blockchain()
            blockchain.import_state(state)
            
            self.logger.debug("Blockchain state loaded successfully")
            return blockchain
            
        except Exception as e:
            self.logger.error(f"Error loading blockchain state: {str(e)}")
            raise BlockchainError(f"State load failed: {str(e)}")

    async def _initialize_test_wallets(self, blockchain: Blockchain):
        """Initialize test wallets with funds from genesis wallet"""
        try:
            transactions = []
        
            # Add mining reward transaction first
            reward_tx = Transaction.create_reward(
                recipient=self.genesis_wallet.address,
                amount=blockchain.get_block_reward(len(blockchain.chain))
            )
            transactions.append(reward_tx)
        
            # Create test wallets and funding transactions
            for i in range(5):
                wallet = Wallet.generate_new()
                self.test_wallets.append(wallet)
                self.logger.debug(f"Created test wallet {i+1} with address: {wallet.address}")
            
                funding_tx = Transaction(
                    sender=self.genesis_wallet.address,
                    recipient=wallet.address,
                    amount=Decimal('1000000.0'),
                    nonce=i
                )
            
                signature = self.genesis_wallet.sign_message(funding_tx.to_string())
                funding_tx.set_signature(signature)
            
                if funding_tx.verify_transaction(blockchain):
                    transactions.append(funding_tx)
                else:
                    raise BlockchainError(f"Failed to verify funding transaction {i+1}")

            # Create funding block
            block = Block(
                height=len(blockchain.chain),
                previous_hash=blockchain.chain[-1].hash,
                transactions=transactions,
                timestamp=int(time.time()),
                validator=self.genesis_wallet.address
            )

            if blockchain.add_block(block):
                self.logger.info(f"Added funding block with {len(transactions)} transactions")
                await self._save_blockchain_state()
            
                # Verify balances
                for wallet in self.test_wallets:
                    balance = blockchain.get_balance(wallet.address)
                    self.logger.info(f"Wallet {wallet.address} balance: {balance}")
            else:
                raise BlockchainError("Failed to add funding block")

        except Exception as e:
            self.logger.error(f"Error initializing test wallets: {str(e)}")
            raise BlockchainError(f"Wallet initialization failed: {str(e)}")

    def _create_node(self, node_index: int, blockchain: Blockchain) -> Node:
        """Create and initialize a testnet node"""
        port = self.base_port + node_index
        self.logger.debug(f"Creating node {node_index} on port {port}")
        
        # Create node directory
        node_dir = self.config_dir / f"node_{node_index}"
        node_dir.mkdir(exist_ok=True)
        
        try:
            node = Node(
                host="127.0.0.1",
                port=port,
                blockchain=blockchain,
            )

            # Debug current state before registration
            self.logger.debug(f"Before registration - Blockchain pos_consensus validators: {blockchain.pos_consensus.validators}")
            self.logger.debug(f"Before registration - Blockchain pos_consensus active validators: {blockchain.pos_consensus.active_validators}")
        

           # Register node as validator with initial stake
            initial_stake = Decimal('2000')  # Set initial stake
            self.logger.debug(f"Registering node {node.address} as validator with stake {initial_stake}")
            success = blockchain.pos_consensus.add_validator(  # Changed from register_validator to add_validator
                node.address,
                initial_stake
            )
            self.logger.debug(f"Validator registration success: {success}")
            self.logger.debug(f"Active validators after registration: {blockchain.pos_consensus.get_active_validators()}")

            # Debug state after registration
            self.logger.debug(f"After registration - Blockchain pos_consensus validators: {blockchain.pos_consensus.validators}")
            self.logger.debug(f"After registration - Blockchain pos_consensus active validators: {blockchain.pos_consensus.active_validators}")
            self.logger.debug(f"Node's pos_consensus active validators: {node.pos_consensus.active_validators}")
            

            # Fund node's validator address
            funding_tx = Transaction(
                sender=self.genesis_wallet.address,
                recipient=node.address,
                amount=Decimal('2000'),  # Extra for staking
                nonce=node_index
            )
            signature = self.genesis_wallet.sign_message(funding_tx.to_string())
            funding_tx.set_signature(signature)
        
            # Add funding transaction to blockchain
            if funding_tx.verify_transaction(blockchain):
                blockchain.add_transaction_to_mempool(funding_tx)
        

            self.logger.debug(f"Successfully created node {node_index}")
            self.logger.info(f"Registered node {node_index} as validator with stake {initial_stake}")
            
            return node
            
        except Exception as e:
            self.logger.error(f"Failed to create node {node_index}: {str(e)}")
            raise BlockchainError(f"Node creation failed: {str(e)}")

    async def _start_nodes(self):
        """Start all nodes in parallel and wait for them to be ready"""
        try:
            # Create tasks for starting nodes
            start_tasks = []
            for node in self.test_nodes:
                task = asyncio.create_task(node.start())
                start_tasks.append(task)

            # Wait for all nodes to start
            await asyncio.gather(*start_tasks)
            await asyncio.sleep(2)  # Give nodes time to fully initialize
            
            self.logger.info(f"Started {len(self.test_nodes)} nodes")
            
        except Exception as e:
            self.logger.error(f"Error starting nodes: {str(e)}")
            raise BlockchainError(f"Node startup failed: {str(e)}")

    async def _connect_nodes(self):
        """Connect all nodes to each other"""
        try:
            for i, node in enumerate(self.test_nodes):
                for j, peer_node in enumerate(self.test_nodes):
                    if i != j:
                        handshake_data = {
                            "type": "handshake",
                            "payload": {
                                "node_id": f"node_{i}",
                                "host": "127.0.0.1",
                                "port": self.base_port + j,
                                "version": "1.0.0"
                            },
                            "sender": f"node_{i}"
                        }
                        success = await node.connect_to_peer(
                            ("127.0.0.1", self.base_port + j),
                            handshake_data
                        )
                        if success:
                            self.logger.debug(f"Connected node {i} to node {j}")
                        else:
                            self.logger.warning(f"Failed to connect node {i} to node {j}")
                            
        except Exception as e:
            self.logger.error(f"Error connecting nodes: {str(e)}")
            raise BlockchainError(f"Node connection failed: {str(e)}")

    async def _save_config(self):
        """Save testnet configuration"""
        try:
            config = {
                "nodes": [
                    {
                        "id": i,
                        "host": "127.0.0.1",
                        "port": self.base_port + i
                    }
                    for i in range(len(self.test_nodes))
                ],
                "genesis_wallet": {
                    "address": self.genesis_wallet.address,
                    "private_key": self.genesis_wallet.export_private_key()
                }
            }
        
            # Add test wallets if they exist
            if hasattr(self, 'test_wallets') and self.test_wallets:
                config["test_wallets"] = [
                    {
                        "address": wallet.address,
                        "private_key": wallet.export_private_key()
                    }
                    for wallet in self.test_wallets
                ]
        
            config_file = self.config_dir / "testnet_config.json"
            async with aiofiles.open(config_file, "w") as f:
                await f.write(json.dumps(config, indent=2))
            
            self.logger.debug(f"Configuration saved successfully to {config_file}")
        
        except Exception as e:
            self.logger.error(f"Error saving configuration: {str(e)}")
            raise BlockchainError(f"Config save failed: {str(e)}")
        
    async def initialize_testnet(self, num_nodes: int = 3):
        """Initialize testnet with specified number of nodes"""
        self.logger.info(f"Initializing testnet with {num_nodes} nodes")
    
        try:
            # Clean up existing testnet if it exists
            if self.config_dir.exists():
                shutil.rmtree(self.config_dir)
        
            # Create config directory
            self.config_dir.mkdir(exist_ok=True)
        
            # Create genesis block and initial blockchain
            self.blockchain = self._create_genesis_blockchain()
        
            # Save initial blockchain state
            await self._save_blockchain_state()
        
            # Initialize test wallets
            await self._initialize_test_wallets(self.blockchain)

            # Save configuration early to ensure it exists
            await self._save_config()
        
            # Initialize nodes
            for i in range(num_nodes):
                node = self._create_node(i, self.blockchain)
                self.test_nodes.append(node)
        
            # Start nodes
            self.running = True
            await self._start_nodes()
        
            # Connect nodes
            await self._connect_nodes()
        
            
        
            # Save final blockchain state
            await self._save_blockchain_state()
        
            self.logger.info("Testnet initialization complete")
        
            # Print success message
            print("\nTestnet initialized successfully!")
            print("Configuration saved to: testnet_data/testnet_config.json")
            print("Press Ctrl+C to stop the testnet")
        
            # Keep testnet running until shutdown is requested
            while self.running:
                await asyncio.sleep(1)
                if self.shutdown_event.is_set():
                    break
            
        except Exception as e:
            self.logger.error(f"Error during testnet initialization: {str(e)}")
            raise BlockchainError(f"Testnet initialization failed: {str(e)}")
        finally:
            await self.stop_testnet()

    async def start_testnet(self):
        """Start the testnet"""
        try:
            # Load blockchain state
            self.blockchain = await self._load_blockchain_state()
            
            # Load existing configuration
            config_file = self.config_dir / "testnet_config.json"
            async with aiofiles.open(config_file, "r") as f:
                config = json.loads(await f.read())

            # Create nodes from config
            for node_config in config["nodes"]:
                node = Node(
                    host=node_config["host"],
                    port=node_config["port"],
                    blockchain=self.blockchain
                )
                self.test_nodes.append(node)

            # Start nodes and keep them running
            self.running = True
            await self._start_nodes()
            
            # Connect nodes
            await self._connect_nodes()
            
            self.logger.info("Testnet started successfully")
            
            # Keep testnet running until shutdown is requested
            await self.shutdown_event.wait()
            
        except Exception as e:
            self.logger.error(f"Error starting testnet: {str(e)}")
            raise
        finally:
            await self.stop_testnet()

    async def stop_testnet(self):
        """Stop the testnet"""
        if not self.running:  # Skip if already stopping
            return
        
        self.running = False
        try:
            # Cancel all running tasks
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            for task in tasks:
                task.cancel()
            
            # Stop all nodes
            for node in self.test_nodes:
                await node.stop()
        
            # Save final blockchain state
            if hasattr(self, 'blockchain'):
                await self._save_blockchain_state()
                
            self.logger.info("Testnet stopped")
        
            # Force exit
            os._exit(0)
            
        except Exception as e:
            self.logger.error(f"Error stopping testnet: {str(e)}")
            os._exit(1)

    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals"""
        if self.running:  # Add this check
            self.logger.info("Shutdown signal received")
            self.running = False  # Add this line
            if not self.shutdown_event.is_set():
                self.shutdown_event.set()
                # Force cleanup after a short delay if still running
                loop = asyncio.get_event_loop()
                if loop and loop.is_running():
                    loop.call_later(3, lambda: os._exit(0))

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
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, testnet.handle_shutdown)
    signal.signal(signal.SIGTERM, testnet.handle_shutdown)
    
    # Create and configure event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        if args.action == "init":
            if not loop.is_running():
                loop.run_until_complete(testnet.initialize_testnet(args.nodes))
        elif args.action == "start":
            if not (Path("testnet_data") / "testnet_config.json").exists():
                print("Testnet not initialized. Run with --action init first")
                return
            if not loop.is_running():
                loop.run_until_complete(testnet.start_testnet())
        elif args.action == "stop":
            if not loop.is_running():
                loop.run_until_complete(testnet.stop_testnet())
            
    except KeyboardInterrupt:
        print("\nShutdown requested...")
        if not loop.is_running():
            loop.run_until_complete(testnet.stop_testnet())
    except Exception as e:
        logging.error(f"Error in main: {str(e)}")
        if not loop.is_running():
            loop.run_until_complete(testnet.stop_testnet())
        sys.exit(1)
    finally:
        try:
            # Cancel all running tasks
            pending = asyncio.all_tasks(loop)
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                
            # Close the event loop
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
        except Exception as e:
            logging.error(f"Error during cleanup: {str(e)}")

if __name__ == "__main__":
    main()