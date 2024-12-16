#consensus/_init_.py
from .proof_of_stake import ProofOfStake
from .validator import Validator

__all__ = ['ProofOfStake', 'Validator']