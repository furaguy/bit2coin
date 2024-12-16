# src/crypto/signature.py
from typing import Optional
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature
import base64
import hashlib
import base58

class SignatureManager:
    """
    Handles digital signatures for transactions
    """
    def __init__(self, private_key: Optional[str] = None):
        """Initialize with optional private key"""
        if private_key:
            self.private_key = self._load_private_key(private_key)
        else:
            self.private_key = self._generate_private_key()
            
        self.public_key = self.private_key.public_key()

    def _generate_private_key(self) -> rsa.RSAPrivateKey:
        """Generate a new RSA private key"""
        return rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )

    def _load_private_key(self, key_str: str) -> rsa.RSAPrivateKey:
        """Load private key from string"""
        try:
            key_bytes = base64.b64decode(key_str)
            return serialization.load_pem_private_key(
                key_bytes,
                password=None
            )
        except Exception as e:
            raise ValueError(f"Invalid private key: {str(e)}")

    def get_private_key_string(self) -> str:
        """Export private key as base64 string"""
        key_bytes = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        return base64.b64encode(key_bytes).decode()

    def get_public_key_string(self) -> str:
        """Export public key as base64 string"""
        key_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return base64.b64encode(key_bytes).decode()

    def sign_data(self, data: str) -> str:
        """Sign data and return signature"""
        try:
            signature = self.private_key.sign(
                data.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return base64.b64encode(signature).decode()
        except Exception as e:
            raise ValueError(f"Signing failed: {str(e)}")

    def verify_data(self, data: str, signature: str, public_key_str: Optional[str] = None) -> bool:
        """Verify signed data"""
        try:
            signature_bytes = base64.b64decode(signature)
            verify_key = self.public_key
            
            if public_key_str:
                key_bytes = base64.b64decode(public_key_str)
                verify_key = serialization.load_pem_public_key(key_bytes)

            verify_key.verify(
                signature_bytes,
                data.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except (InvalidSignature, ValueError):
            return False

    def get_address(self) -> str:
        """Generate blockchain address from public key"""
        public_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        # SHA-256 hash
        sha256_hash = hashlib.sha256(public_bytes).digest()
        
        # RIPEMD-160 hash
        ripemd160_hash = hashlib.new('ripemd160', sha256_hash).digest()
        
        # Add version byte (0x00 for mainnet)
        versioned_hash = b'\x00' + ripemd160_hash
        
        # Double SHA-256 for checksum
        checksum = hashlib.sha256(
            hashlib.sha256(versioned_hash).digest()
        ).digest()[:4]
        
        # Combine version, hash, and checksum
        binary_address = versioned_hash + checksum
        
        # Base58 encode
        address = base58.b58encode(binary_address).decode('ascii')
        return address