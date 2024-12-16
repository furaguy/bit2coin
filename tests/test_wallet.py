# test_wallet.py
import pytest
from src.wallet.wallet import Wallet
from src.wallet.keys import KeyPair
from src.blockchain.blockchain import Blockchain
from src.blockchain.block import Block
from src.blockchain.transaction import Transaction
from src.crypto.hash import Hash
import time

class TestWallet:
    @pytest.fixture
    def wallet(self):
        return Wallet(KeyPair.generate())
    
    @pytest.fixture
    def blockchain(self):
        return Blockchain()

    def test_wallet_creation(self, wallet):
        assert wallet.keypair is not None
        assert wallet.address is not None
        assert len(wallet.address) == 40  # RIPEMD160 hash length
        
    def test_transaction_creation(self, wallet):
        recipient_address = "recipient_address"
        amount = 10.0
        
        # Test with insufficient balance
        tx = wallet.create_transaction(recipient_address, amount)
        assert tx is None
        
        # Set some balance and try again
        wallet.balance = 20.0
        tx = wallet.create_transaction(recipient_address, amount)
        assert tx is not None
        assert tx.sender == wallet.address
        assert tx.recipient == recipient_address
        assert tx.amount == amount
        assert tx.verify_signature() == True
        
    def test_balance_update(self, wallet, blockchain):
        recipient_wallet = Wallet(KeyPair.generate())
        
        # Create transaction to wallet
        tx = Transaction(
            sender="genesis",
            recipient=wallet.address,
            amount=100.0,
            timestamp=int(time.time())
        )
        
        # Add transaction to blockchain
        new_block = Block(
            index=len(blockchain.chain),
            transactions=[tx],
            previous_hash=blockchain.chain[-1].hash,
            timestamp=int(time.time())
        )
        blockchain.add_block(new_block)
        
        # Update wallet balance
        wallet.update_balance(blockchain)
        assert wallet.balance == 100.0
        
        # Create and add outgoing transaction
        tx2 = Transaction(
            sender=wallet.address,
            recipient=recipient_wallet.address,
            amount=30.0,
            timestamp=int(time.time())
        )
        new_block = Block(
            index=len(blockchain.chain),
            transactions=[tx2],
            previous_hash=blockchain.chain[-1].hash,
            timestamp=int(time.time())
        )
        blockchain.add_block(new_block)
        
        wallet.update_balance(blockchain)
        assert wallet.balance == 70.0
        
    def test_export_credentials(self, wallet):
        credentials = wallet.export_public_credentials()
        assert "address" in credentials
        assert "public_key" in credentials
        assert credentials["address"] == wallet.address