# test_blockchain.py
import pytest
from datetime import datetime
from src.blockchain.block import Block
from src.blockchain.blockchain import Blockchain
from src.blockchain.transaction import Transaction
from src.crypto.hash import Hash
from src.wallet.keys import KeyPair

class TestBlockchain:
    @pytest.fixture
    def blockchain(self):
        return Blockchain()
    
    @pytest.fixture
    def sample_transaction(self):
        sender_keypair = KeyPair.generate()
        recipient_keypair = KeyPair.generate()
        tx = Transaction(
            sender=Hash.hash_public_key(sender_keypair.public_key),
            recipient=Hash.hash_public_key(recipient_keypair.public_key),
            amount=10.0,
            timestamp=int(datetime.now().timestamp())
        )
        tx.set_signature(sender_keypair.sign(tx.to_string()))
        return tx

    def test_genesis_block_creation(self, blockchain):
        assert len(blockchain.chain) == 1
        assert blockchain.chain[0].previous_hash == "0" * 64
        
    def test_add_block(self, blockchain, sample_transaction):
        new_block = Block(
            index=len(blockchain.chain),
            transactions=[sample_transaction],
            previous_hash=blockchain.chain[-1].hash,
            timestamp=int(datetime.now().timestamp())
        )
        assert blockchain.add_block(new_block) == True
        assert len(blockchain.chain) == 2
        assert blockchain.chain[-1].hash == new_block.hash
        
    def test_validate_chain(self, blockchain, sample_transaction):
        # Add valid block
        new_block = Block(
            index=len(blockchain.chain),
            transactions=[sample_transaction],
            previous_hash=blockchain.chain[-1].hash,
            timestamp=int(datetime.now().timestamp())
        )
        blockchain.add_block(new_block)
        assert blockchain.is_valid() == True
        
        # Tamper with transaction
        blockchain.chain[-1].transactions[0].amount = 999999
        assert blockchain.is_valid() == False
        
    def test_get_balance(self, blockchain, sample_transaction):
        new_block = Block(
            index=len(blockchain.chain),
            transactions=[sample_transaction],
            previous_hash=blockchain.chain[-1].hash,
            timestamp=int(datetime.now().timestamp())
        )
        blockchain.add_block(new_block)
        
        sender_balance = blockchain.get_balance(sample_transaction.sender)
        recipient_balance = blockchain.get_balance(sample_transaction.recipient)
        
        assert sender_balance == -10.0
        assert recipient_balance == 10.0