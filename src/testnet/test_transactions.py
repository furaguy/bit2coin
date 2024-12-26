# src/testnet/test_transactions.py

import sys
from pathlib import Path
import json
import asyncio
from decimal import Decimal
import time
import logging
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
import aiofiles
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent.parent 
sys.path.append(str(project_root))

from src.blockchain.transaction import Transaction, TransactionType, TransactionStatus
from src.wallet.wallet import Wallet
from src.blockchain.blockchain import Blockchain, BlockchainError

# Configuration constants
MAX_RETRIES = 10
RETRY_DELAY = 1  # seconds
BLOCK_PRODUCTION_TIMEOUT = 60  # seconds

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("testnet-transactions")

@dataclass 
class TransactionStatus:
    status: str
    tx_id: str
    confirmations: int = 0
    block_height: Optional[int] = None
    block_hash: Optional[str] = None

class TestnetClient:
    def __init__(self, base_port: int = 6000, num_nodes: int = 3):
        self.base_port = base_port
        self.num_nodes = num_nodes
        self.node_id = f"test_client_{int(time.time())}"
        self.logger = logging.getLogger("testnet-client")
        self.config = None
        self.genesis_wallet = None
        self.blockchain = None
        self._initialize_client()

    def _load_testnet_config(self) -> Dict:
        """Load testnet configuration"""
        try:
            config_path = Path("testnet_data") / "testnet_config.json"
            logger.debug(f"Loading config from: {config_path}")
            
            if not config_path.exists():
                logger.error(f"Config file not found at: {config_path}")
                raise FileNotFoundError(f"Config file not found at: {config_path}")
                
            with open(config_path, 'r') as f:
                config = json.load(f)
                logger.debug(f"Loaded testnet config: {json.dumps(config, indent=2)}")
                return config
        except Exception as e:
            self.logger.error(f"Error loading testnet config: {str(e)}")
            raise

    def _initialize_client(self):
        """Initialize client with testnet configuration"""
        try:
            self.config = self._load_testnet_config()
            self.blockchain = Blockchain()
            
            logger.debug(f"Config genesis wallet: {self.config.get('genesis_wallet', {})}")
            
            if 'genesis_wallet' in self.config:
                private_key = self.config['genesis_wallet']['private_key']
                logger.debug(f"Loading genesis wallet with private key: {private_key[:10]}...")
                
                self.genesis_wallet = Wallet(private_key=private_key)
                
                expected_address = self.config['genesis_wallet']['address'] 
                address_matches = self.genesis_wallet.address == expected_address
                logger.debug(f"Loaded genesis wallet. Address matches config: {address_matches}")
                if not address_matches:
                    logger.warning(f"Expected address: {expected_address}")
                    logger.warning(f"Generated address: {self.genesis_wallet.address}")
                
                logger.info(f"Loaded genesis wallet with address: {self.genesis_wallet.address}")
            else:
                raise ValueError("Genesis wallet not found in config")

        except Exception as e:
            logger.error(f"Error initializing testnet client: {str(e)}")
            raise

    async def send_message_to_node(self, port: int, message: dict) -> Optional[dict]:
        """Send message to node and get response"""
        try:
            logger.debug(f"Connecting to node at port {port}")
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            
            data = json.dumps(message).encode()
            writer.write(len(data).to_bytes(4, 'big'))
            writer.write(data)
            await writer.drain()
            
            logger.debug(f"Sent message to port {port}: {json.dumps(message, indent=2)}")
            
            length_data = await reader.read(4)
            if not length_data:
                logger.warning(f"No response from port {port}")
                return None
                
            message_length = int.from_bytes(length_data, 'big')
            response_data = await reader.read(message_length)
            
            if response_data:
                response = json.loads(response_data.decode())
                logger.debug(f"Received response from port {port}: {json.dumps(response, indent=2)}")
                return response
            return None
            
        except Exception as e:
            self.logger.error(f"Error communicating with node on port {port}: {str(e)}")
            return None
        finally:
            if 'writer' in locals():
                writer.close()
                await writer.wait_closed()

    async def get_transaction_status(self, tx_id: str, port: int) -> Optional[TransactionStatus]:
        """Get transaction status from a specific node with improved error handling"""
        try:
            message = {
                "type": "transaction_status", 
                "payload": {"tx_id": tx_id},
                "sender": self.node_id
            }
            
            self.logger.debug(f"Checking transaction status for {tx_id} on port {port}")
            response = await self.send_message_to_node(port, message)
            
            if response and response.get("payload"):
                payload = response["payload"]
                self.logger.debug(f"Received status response: {payload}")
                return TransactionStatus(
                    status=payload.get("status", "unknown"),
                    tx_id=payload.get("tx_id", tx_id),
                    confirmations=payload.get("confirmations", 0),
                    block_height=payload.get("block_height"),
                    block_hash=payload.get("block_hash")
                )
            
            self.logger.warning(f"Received invalid status response: {response}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting transaction status: {str(e)}", exc_info=True)
            return None

    async def wait_for_transaction_confirmation(
        self, 
        tx_id: str, 
        port: int, 
        max_retries: int = MAX_RETRIES,
        retry_delay: int = RETRY_DELAY
    ) -> bool:
        """Wait for transaction confirmation with timeout"""
        self.logger.info(f"Waiting for confirmation of transaction {tx_id}")
        
        for retry in range(max_retries):
            try:
                status = await self.get_transaction_status(tx_id, port)
                if status:
                    self.logger.debug(
                        f"Transaction status check {retry + 1}/{max_retries}: "
                        f"status={status.status}, confirmations={status.confirmations}"
                    )
                    
                    if status.status == "confirmed":
                        self.logger.info(
                            f"Transaction confirmed after {retry + 1} attempts "
                            f"with {status.confirmations} confirmations"
                        )
                        return True
                        
                    elif status.status == "error":
                        self.logger.error(f"Transaction failed: {status.tx_id}")
                        return False
                        
                await asyncio.sleep(retry_delay)
                
            except Exception as e:
                self.logger.error(
                    f"Error checking transaction status (attempt {retry + 1}): {str(e)}", 
                    exc_info=True
                )
                
        self.logger.error(
            f"Transaction not confirmed after {max_retries} attempts"
        )
        return False

    async def get_wallet_balance(self, address: str, port: int) -> Optional[Decimal]:
        """Get wallet balance from a specific node"""
        message = {
            "type": "get_balance",
            "payload": {"address": address},
            "sender": self.node_id
        }
        
        logger.debug(f"Requesting balance for address {address} from port {port}")
        response = await self.send_message_to_node(port, message)
        if response and response.get("payload", {}).get("status") == "success":
            balance = Decimal(response["payload"]["balance"])
            logger.debug(f"Received balance for {address}: {balance}")
            return balance
        else:
            logger.warning(f"Failed to get balance for {address}. Response: {response}")
        return None

    async def broadcast_transaction(self, transaction: Transaction) -> bool:
        """Broadcast transaction to all nodes"""
        message = {
            "type": "transaction",
            "payload": {
                "transaction": transaction.to_dict(),
                "propagate": True
            },
            "sender": self.node_id
        }
        
        logger.debug(f"Broadcasting transaction: {json.dumps(transaction.to_dict(), indent=2)}")
        
        results = []
        for port in range(self.base_port, self.base_port + self.num_nodes):
            try:
                response = await self.send_message_to_node(port, message)
                if response and response.get("payload", {}).get("status") == "accepted":
                    self.logger.info(f"Transaction accepted by node on port {port}")
                    results.append(True)
                else:
                    self.logger.warning(f"Transaction rejected by node on port {port}: {response}")
                    results.append(False)
            except Exception as e:
                self.logger.error(f"Failed to broadcast to node on port {port}: {str(e)}")
                results.append(False)
        
        return any(results)

class TransactionTest:
    def __init__(self, client: TestnetClient):
        self.client = client
        self.test_wallets: List[Wallet] = []
        self.logger = logging.getLogger("transaction-test")
        self._load_test_wallets()

    def _load_test_wallets(self):
        """Load test wallets from config"""
        if 'test_wallets' in self.client.config:
            for wallet_data in self.client.config['test_wallets']:
                wallet = Wallet(private_key=wallet_data['private_key'])
                self.test_wallets.append(wallet)
                logger.debug(f"Loaded test wallet: {wallet.address}")

    async def run_basic_transaction_test(self) -> bool:
        """Run basic transaction test between test wallets"""
        if len(self.test_wallets) < 2:
            logger.error("Insufficient test wallets")
            return False

        try:
            # Setup test parameters
            sender = self.test_wallets[0]
            recipient = self.test_wallets[1]
            amount = Decimal("10.0")
            test_start_time = datetime.now()

            # Check sender balance
            sender_balance = await self.client.get_wallet_balance(
                sender.address, 
                self.client.base_port
            )
            
            if not sender_balance or sender_balance < amount:
                self.logger.error(
                    f"Insufficient balance for test: {sender_balance}"
                )
                return False

            # Create and sign transaction
            self.logger.info(f"Creating test transaction for {amount} from {sender.address} to {recipient.address}")
            tx = Transaction(
                sender=sender.address,
                recipient=recipient.address,  
                amount=amount,
                transaction_type=TransactionType.TRANSFER
            )
            signature = sender.sign_message(tx.to_string())
            tx.set_signature(signature)

            # Broadcast transaction
            success = await self.client.broadcast_transaction(tx)
            if not success:
                self.logger.error("Failed to broadcast transaction")
                return False

            # Wait for confirmation with timeout
            confirmation_success = await self.client.wait_for_transaction_confirmation(
                tx.transaction_id,
                self.client.base_port
            )

            if confirmation_success:
                # Verify final balances
                new_sender_balance = await self.client.get_wallet_balance(
                    sender.address,
                    self.client.base_port
                )
                new_recipient_balance = await self.client.get_wallet_balance(
                    recipient.address,
                    self.client.base_port
                )
                
                self.logger.info(
                    f"Transaction completed - Balances: "
                    f"Sender: {new_sender_balance}, Recipient: {new_recipient_balance}"
                )
                
                test_duration = (datetime.now() - test_start_time).total_seconds()
                self.logger.info(f"Test completed successfully in {test_duration:.2f} seconds")
                return True
                
            else:
                self.logger.error("Transaction not confirmed within timeout period")
                return False

        except Exception as e:
            self.logger.error(
                f"Error in basic transaction test: {str(e)}", 
                exc_info=True
            )
            return False

    async def run_all_tests(self) -> bool:
        """Run all transaction tests with timeout"""
        try:
            test_results = {}
            
            # Run basic transaction test with timeout
            basic_test_task = asyncio.create_task(self.run_basic_transaction_test())
            try:
                test_results["basic_transaction"] = await asyncio.wait_for(
                    basic_test_task,
                    timeout=BLOCK_PRODUCTION_TIMEOUT
                )
            except asyncio.TimeoutError:
                self.logger.error(
                    f"Basic transaction test timed out after {BLOCK_PRODUCTION_TIMEOUT} seconds"
                )
                test_results["basic_transaction"] = False

            # Log results
            self.logger.info("Test Results:")
            for test_name, result in test_results.items():
                self.logger.info(f"{test_name}: {'PASS' if result else 'FAIL'}")

            return all(test_results.values())

        except Exception as e:
            self.logger.error(f"Error running tests: {str(e)}", exc_info=True)
            return False

async def run_tests():
    """Run the test sequence"""
    try:
        client = TestnetClient()
        tests = TransactionTest(client)
        await tests.run_all_tests()

    except Exception as e:
        logger.error(f"Error in test sequence: {str(e)}")
        logger.exception(e)

def main():
    try:
        logger.debug(f"Current working directory: {Path.cwd()}")
        asyncio.run(run_tests())
    except KeyboardInterrupt:
        logger.info("Tests interrupted by user")
    except Exception as e:
        logger.error(f"Error running tests: {str(e)}")
        logger.exception(e)

if __name__ == "__main__":
    main()