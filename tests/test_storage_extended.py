# tests/test_storage_extended.py
import pytest
import asyncio
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from src.storage.blockchain_state import BlockchainState
from src.storage.chain_reorg import ChainReorganizer
from src.storage.checkpoints import CheckpointManager
from src.blockchain.block import Block
from src.blockchain.transaction import Transaction
from src.wallet.keys import KeyPair

class TestStorageExtended:
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
    def state(self, db_path):
        """Create a test blockchain state instance"""
        state = BlockchainState(db_path)
        yield state
        state.close()

    @pytest.fixture
    def sample_blocks(self):
        """Create a sequence of test blocks"""
        blocks = []
        prev_hash = "0" * 64
        
        for i in range(5):
            tx = Transaction(
                sender="genesis",
                recipient=f"recipient_{i}",
                amount=100.0,
                timestamp=int(datetime.now().timestamp())
            )
            
            block = Block(
                index=i,
                transactions=[tx],
                previous_hash=prev_hash,
                timestamp=int(datetime.now().timestamp())
            )
            blocks.append(block)
            prev_hash = block.hash
            
        return blocks

    @pytest.fixture
    def fork_blocks(self, sample_blocks):
        """Create a fork chain of blocks"""
        fork_blocks = []
        prev_hash = sample_blocks[2].hash  # Fork from block 2
        
        for i in range(3, 6):  # Create 3 fork blocks
            tx = Transaction(
                sender="genesis",
                recipient=f"fork_recipient_{i}",
                amount=200.0,
                timestamp=int(datetime.now().timestamp())
            )
            
            block = Block(
                index=i,
                transactions=[tx],
                previous_hash=prev_hash,
                timestamp=int(datetime.now().timestamp())
            )
            fork_blocks.append(block)
            prev_hash = block.hash
            
        return fork_blocks

    @pytest.mark.asyncio
    async def test_block_processing(self, state, sample_blocks):
        """Test basic block processing"""
        # Process blocks
        success = await state.process_new_blocks(sample_blocks)
        assert success == True
        
        # Verify chain state
        metadata = state.get_chain_metadata()
        assert metadata["height"] == len(sample_blocks)
        assert metadata["total_transactions"] == len(sample_blocks)
        
        # Verify chain head
        head = state.get_chain_head()
        assert head == sample_blocks[-1].hash

    @pytest.mark.asyncio
    async def test_chain_reorganization(self, state, sample_blocks, fork_blocks):
        """Test chain reorganization"""
        # First add main chain blocks
        await state.process_new_blocks(sample_blocks[:3])  # Add blocks 0-2
        
        # Then add fork blocks
        success = await state.process_new_blocks(fork_blocks)
        assert success == True
        
        # Verify chain switched to fork
        head = state.get_chain_head()
        assert head == fork_blocks[-1].hash
        
        # Verify balances are correct
        fork_recipient_balance = state.get_balance("fork_recipient_5")
        assert fork_recipient_balance == 200.0

    @pytest.mark.asyncio
    async def test_checkpoint_creation(self, state, sample_blocks):
        """Test checkpoint creation and restoration"""
        # Process blocks
        await state.process_new_blocks(sample_blocks)
        
        # Create checkpoint
        await state.create_periodic_checkpoint()
        
        # Verify checkpoint exists
        checkpoint = await state.checkpoint_manager.get_latest_checkpoint()
        assert checkpoint is not None
        assert checkpoint.height == len(sample_blocks) - 1
        
        # Modify state and restore from checkpoint
        success = await state.restore_from_checkpoint(checkpoint.height)
        assert success == True
        
        # Verify state is restored
        metadata = state.get_chain_metadata()
        assert metadata["height"] == checkpoint.height

    @pytest.mark.asyncio
    async def test_invalid_reorganization(self, state, sample_blocks):
        """Test handling of invalid chain reorganization"""
        # Create invalid blocks (with future timestamps)
        invalid_blocks = []
        prev_hash = sample_blocks[0].hash
        
        for i in range(1, 3):
            tx = Transaction(
                sender="genesis",
                recipient=f"invalid_recipient_{i}",
                amount=100.0,
                timestamp=int((datetime.now() + timedelta(days=1)).timestamp())
            )
            
            block = Block(
                index=i,
                transactions=[tx],
                previous_hash=prev_hash,
                timestamp=int((datetime.now() + timedelta(days=1)).timestamp())
            )
            invalid_blocks.append(block)
            prev_hash = block.hash
            
        # Process initial valid blocks
        await state.process_new_blocks([sample_blocks[0]])
        
        # Attempt invalid reorganization
        success = await state.process_new_blocks(invalid_blocks)
        assert success == False
        
        # Verify chain state remained unchanged
        head = state.get_chain_head()
        assert head == sample_blocks[0].hash

    @pytest.mark.asyncio
    async def test_concurrent_block_processing(self, state, sample_blocks, fork_blocks):
        """Test concurrent block processing"""
        # Create two concurrent tasks
        task1 = asyncio.create_task(state.process_new_blocks(sample_blocks))
        task2 = asyncio.create_task(state.process_new_blocks(fork_blocks))
        
        # Wait for both tasks to complete
        results = await asyncio.gather(task1, task2, return_exceptions=True)
        
        # Verify only one chain was accepted
        metadata = state.get_chain_metadata()
        assert metadata["height"] > 0
        
        head = state.get_chain_head()
        assert head in [sample_blocks[-1].hash, fork_blocks[-1].hash]

    @pytest.mark.asyncio
    async def test_checkpoint_pruning(self, state, sample_blocks):
        """Test checkpoint pruning"""
        # Process blocks in batches to create multiple checkpoints
        for i in range(0, len(sample_blocks), 2):
            batch = sample_blocks[i:i+2]
            await state.process_new_blocks(batch)
            await state.create_periodic_checkpoint()
        
        # Prune old checkpoints
        success = await state.checkpoint_manager.prune_old_checkpoints(keep_count=2)
        assert success == True
        
        # Verify only recent checkpoints remain
        checkpoints = []
        async for key, _ in state.db:
            if key.startswith("checkpoint:") and key != "checkpoint:latest":
                checkpoints.append(key)
        
        assert len(checkpoints) <= 2

    def test_state_cleanup(self, state, sample_blocks):
        """Test proper cleanup of resources"""
        # Process some blocks
        asyncio.run(state.process_new_blocks(sample_blocks))
        
        # Close state
        state.close()
        
        # Verify database is closed
        assert state.db is None

    @pytest.mark.asyncio
    async def test_chain_metrics(self, state, sample_blocks):
        """Test chain metrics calculation"""
        # Process blocks
        await state.process_new_blocks(sample_blocks)
        
        # Get metrics
        metadata = state.get_chain_metadata()
        
        # Verify metrics
        assert metadata["height"] == len(sample_blocks)
        assert metadata["total_transactions"] == len(sample_blocks)
        assert metadata["total_supply"] == sum(
            tx.amount for block in sample_blocks 
            for tx in block.transactions
        )