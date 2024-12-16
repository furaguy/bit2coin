# src/wallet/keys.py
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization
from typing import Tuple, Optional
import base64

class KeyPair:
    def __init__(self, private_key: Optional[rsa.RSAPrivateKey] = None):
        if private_key is None:
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048
            )
        self.private_key = private_key
        self.public_key = private_key.public_key()

    @classmethod
    def generate(cls) -> 'KeyPair':
        """Generate a new keypair"""
        return cls()

    def sign(self, message: str) -> str:
        """Sign a message using the private key"""
        signature = self.private_key.sign(
            message.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode()

    def verify(self, message: str, signature: str) -> bool:
        """Verify a signature using the public key"""
        try:
            signature_bytes = base64.b64decode(signature)
            self.public_key.verify(
                signature_bytes,
                message.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except:
            return False

    def get_address(self) -> str:
        """Generate an address from the public key"""
        public_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return base64.b64encode(public_bytes[:20]).decode()  # Take first 20 bytes for address

    def export_private_key(self) -> str:
        """Export private key in PEM format"""
        private_bytes = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        return private_bytes.decode()

    def export_public_key(self) -> str:
        """Export public key in PEM format"""
        public_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return public_bytes.decode()