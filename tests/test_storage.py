# tests/test_storage.py
import pytest
import os
import tempfile
import shutil
from src.storage.database import Database, DatabaseError
from src.storage.blockchain_state import BlockchainState
from src.blockchain.block import Block
from src.blockchain.transaction import Transaction

class TestStorage:
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test databases"""
        tmp_dir = tempfile.mkdtemp()
        yield tmp_dir
        shutil.rmtree(tmp_dir)

    @pytest.fixture
    def db_path(self, temp_dir):
        """Create a test database path"""
        return os.path.join(temp_dir, "test.db")

    @pytest.fixture
    def database(self, db_path):
        """Create a test database instance"""
        db = Database(db_path)
        yield db
        db.close()

    @pytest.fixture
    def blockchain_state(self, db_path):
        """Create a test blockchain state instance"""
        state = BlockchainState(db_path)
        yield state
        state.close()

    @pytest.fixture
    def sample_transaction(self):
        """Create a sample transaction"""
        return Transaction(
            sender="sender123",
            recipient="recipient456",
            amount=100.0
        )

    @pytest.fixture
    def sample_block(self, sample_transaction):
        """Create a sample block"""
        return Block(
            index=1,
            transactions=[sample_transaction],
            previous_hash="0" * 64
        )

    def test_database_basic_operations(self, database):
        """Test basic database operations"""
        # Test put and get
        database.put("test_key", {"value": "test_value"})
        result = database.get("test_key")
        assert result["value"] == "test_value"

        # Test delete
        assert database.delete("test_key") == True
        assert database.get("test_key") is None

    def test_database_batch_write(self, database):
        """Test batch write operations"""
        test_data = {
            "key1": {"value": "value1"},
            "key2": {"value": "value2"},
            "key3": {"value": "value3"}
        }
        assert database.batch_write(test_data) == True

        for key, expected_value in test_data.items():
            assert database.get(key) == expected_value

    def test_blockchain_state_initialization(self, blockchain_state):
        """Test blockchain state initialization"""
        metadata = blockchain_state.get_chain_metadata()
        assert metadata["height"] == 0
        assert metadata["total_transactions"] == 0
        assert blockchain_state.get_chain_head() is None

    def test_apply_block(self, blockchain_state, sample_block):
        """Test applying a block to the blockchain state"""
        # Apply block
        assert blockchain_state.apply_block(sample_block) == True

        # Verify block storage
        stored_block = blockchain_state.get_block(sample_block.hash)
        assert stored_block is not None
        assert stored_block["hash"] == sample_block.hash

        # Verify chain head
        assert blockchain_state.get_chain_head() == sample_block.hash

        # Verify transaction storage
        tx = sample_block.transactions[0]
        stored_tx = blockchain_state.get_transaction(tx.transaction_id)
        assert stored_tx is not None
        assert stored_tx["transaction_id"] == tx.transaction_id

        # Verify balances
        sender_balance = blockchain_state.get_balance(tx.sender)
        recipient_balance = blockchain_state.get_balance(tx.recipient)
        assert sender_balance == -100.0
        assert recipient_balance == 100.0

    def test_revert_block(self, blockchain_state, sample_block):
        """Test reverting a block from the blockchain state"""
        # First apply the block
        blockchain_state.apply_block(sample_block)

        # Then revert it
        assert blockchain_state.revert_block(sample_block) == True

        # Verify balances are restored
        tx = sample_block.transactions[0]
        sender_balance = blockchain_state.get_balance(tx.sender)
        recipient_balance = blockchain_state.get_balance(tx.recipient)
        assert sender_balance == 0.0
        assert recipient_balance == 0.0

        # Verify chain metadata
        metadata = blockchain_state.get_chain_metadata()
        assert metadata["height"] == 0
        assert metadata["total_transactions"] == 0

    def test_transaction_history(self, blockchain_state, sample_block):
        """Test transaction history tracking"""
        # Apply block
        blockchain_state.apply_block(sample_block)

        # Check sender history
        tx = sample_block.transactions[0]
        sender_history = blockchain_state.get_transaction_history(tx.sender)
        assert len(sender_history) == 1
        assert sender_history[0]["transaction_id"] == tx.transaction_id

        # Check recipient history
        recipient_history = blockchain_state.get_transaction_history(tx.recipient)
        assert len(recipient_history) == 1
        assert recipient_history[0]["transaction_id"] == tx.transaction_id

    def test_error_handling(self, blockchain_state, sample_block):
        """Test error handling in blockchain state"""
        # Try to apply block with insufficient balance
        tx = sample_block.transactions[0]
        tx.amount = 1000000.0  # Amount larger than sender's balance

        # Should fail gracefully
        assert blockchain_state.apply_block(sample_block) == False

        # State should remain unchanged
        metadata = blockchain_state.get_chain_metadata()
        assert metadata["height"] == 0
        assert metadata["total_transactions"] == 0