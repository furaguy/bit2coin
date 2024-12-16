# test_consensus.py
import pytest
from src.consensus.proof_of_stake import ProofOfStake
from src.consensus.validator import Validator
from src.wallet.keys import KeyPair
from src.blockchain.block import Block
from src.blockchain.transaction import Transaction
from datetime import datetime, timedelta

class TestConsensus:
    @pytest.fixture
    def pos_system(self):
        return ProofOfStake()
    
    @pytest.fixture
    def validator(self):
        keypair = KeyPair.generate()
        return Validator(
            address=keypair.get_address(),
            stake=1000.0,
            keypair=keypair
        )
    
    @pytest.fixture
    def sample_block(self):
        return Block(
            index=1,
            transactions=[],
            previous_hash="0" * 64,
            timestamp=int(datetime.now().timestamp())
        )

    def test_validator_registration(self, pos_system, validator):
        assert pos_system.register_validator(validator) == True
        assert len(pos_system.get_validators()) == 1
        
    def test_stake_calculation(self, pos_system, validator):
        pos_system.register_validator(validator)
        selected_validator = pos_system.select_validator()
        assert selected_validator is not None
        assert selected_validator.stake == 1000.0
        
    def test_validator_block_validation(self, validator, sample_block):
        assert validator.validate_block(sample_block) == True
        
        # Test with invalid block
        sample_block.timestamp = int((datetime.now() + timedelta(days=1)).timestamp())
        assert validator.validate_block(sample_block) == False
        
    def test_validator_priority(self, validator):
        current_time = int(datetime.now().timestamp())
        validator.last_validation_time = current_time - 3600  # 1 hour ago
        
        priority = validator.calculate_priority(current_time)
        assert priority > 0
        assert priority == validator.stake * 3600
        
    def test_stake_update(self, pos_system, validator):
        pos_system.register_validator(validator)
        pos_system.update_validator_stake(validator.address, 2000.0)
        
        updated_validator = pos_system.get_validator(validator.address)
        assert updated_validator.stake == 2000.0