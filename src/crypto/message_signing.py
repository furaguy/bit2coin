# File: src/crypto/message_signing.py

from typing import Dict, Optional, Union
import json
import time
from dataclasses import asdict
from hashlib import sha256
import ecdsa
import base64

class KeyPair:
    def __init__(self, private_key: Optional[str] = None):
        """Initialize a key pair for signing."""
        if private_key:
            # Load existing private key
            self.signing_key = ecdsa.SigningKey.from_string(
                bytes.fromhex(private_key),
                curve=ecdsa.SECP256k1
            )
        else:
            # Generate new key pair
            self.signing_key = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1)
        
        self.verifying_key = self.signing_key.get_verifying_key()

    @property
    def private_key(self) -> str:
        """Get private key as hex string."""
        return self.signing_key.to_string().hex()

    @property
    def public_key(self) -> str:
        """Get public key as hex string."""
        return self.verifying_key.to_string().hex()

class MessageSigner:
    def __init__(self, key_pair: KeyPair):
        self.key_pair = key_pair

    def sign_message(self, message: Union[Dict, bytes, str]) -> str:
        """Sign a message using the private key."""
        if isinstance(message, dict):
            message = json.dumps(message, sort_keys=True).encode()
        elif isinstance(message, str):
            message = message.encode()

        signature = self.key_pair.signing_key.sign(
            message,
            hashfunc=sha256
        )
        return base64.b64encode(signature).decode()

    @staticmethod
    def verify_signature(
        message: Union[Dict, bytes, str],
        signature: str,
        public_key: str
    ) -> bool:
        """Verify a message signature using the public key."""
        try:
            if isinstance(message, dict):
                message = json.dumps(message, sort_keys=True).encode()
            elif isinstance(message, str):
                message = message.encode()

            verifying_key = ecdsa.VerifyingKey.from_string(
                bytes.fromhex(public_key),
                curve=ecdsa.SECP256k1
            )
            signature_bytes = base64.b64decode(signature)
            return verifying_key.verify(
                signature_bytes,
                message,
                hashfunc=sha256
            )
        except Exception:
            return False

class SignedMessage:
    def __init__(
        self,
        message_type: str,
        data: Dict,
        sender: str,
        signer: MessageSigner
    ):
        self.type = message_type
        self.data = data
        self.sender = sender
        self.timestamp = int(time.time())
        self.signature = self._generate_signature(signer)

    def _generate_signature(self, signer: MessageSigner) -> str:
        """Generate signature for the message."""
        message_data = {
            "type": self.type,
            "data": self.data,
            "sender": self.sender,
            "timestamp": self.timestamp
        }
        return signer.sign_message(message_data)

    def verify(self, public_key: str) -> bool:
        """Verify the message signature."""
        message_data = {
            "type": self.type,
            "data": self.data,
            "sender": self.sender,
            "timestamp": self.timestamp
        }
        return MessageSigner.verify_signature(
            message_data,
            self.signature,
            public_key
        )

    def to_dict(self) -> Dict:
        """Convert to dictionary format."""
        return {
            "type": self.type,
            "data": self.data,
            "sender": self.sender,
            "timestamp": self.timestamp,
            "signature": self.signature
        }

# Update ConsensusNetwork class to use message signing
class SecureConsensusMessage:
    """Helper class for handling secure consensus messages."""
    
    def __init__(self, signer: MessageSigner):
        self.signer = signer

    def create_block_message(self, block: Dict) -> SignedMessage:
        """Create a signed block message."""
        return SignedMessage(
            message_type="new_block",
            data=block,
            sender=self.signer.key_pair.public_key,
            signer=self.signer
        )

    def create_vote_message(
        self,
        block_hash: str,
        block_height: int,
        validator: str
    ) -> SignedMessage:
        """Create a signed vote message."""
        return SignedMessage(
            message_type="block_vote",
            data={
                "block_hash": block_hash,
                "block_height": block_height,
                "validator": validator
            },
            sender=self.signer.key_pair.public_key,
            signer=self.signer
        )

    def create_slashing_message(self, event: Dict) -> SignedMessage:
        """Create a signed slashing event message."""
        return SignedMessage(
            message_type="slashing_event",
            data=event,
            sender=self.signer.key_pair.public_key,
            signer=self.signer
        )

    @staticmethod
    def verify_message(
        message: Dict,
        public_key: str
    ) -> bool:
        """Verify a received message."""
        signed_message = SignedMessage(
            message_type=message["type"],
            data=message["data"],
            sender=message["sender"],
            signer=None  # Not needed for verification
        )
        signed_message.signature = message["signature"]
        signed_message.timestamp = message["timestamp"]
        return signed_message.verify(public_key)