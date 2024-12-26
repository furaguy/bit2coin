#src/crypto/signature.py
from typing import Optional
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives import serialization
import base58
import hashlib
import base64

class SignatureManager:
    """
    Handles digital signatures for transactions
    """
    
    def __init__(self, private_key: Optional[str | rsa.RSAPrivateKey] = None):
        """Initialize with optional private key string or RSAPrivateKey object"""
        if private_key is None:
            # Generate new private key if none provided
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048
            )
        elif isinstance(private_key, str):
            # Convert PEM string to RSAPrivateKey object
            try:
                private_key = serialization.load_pem_private_key(
                    private_key.encode(),
                    password=None
                )
            except Exception as e:
                raise ValueError(f"Invalid private key format: {str(e)}")
                
        self.private_key = private_key
        self.public_key = private_key.public_key()

    def get_private_key_string(self) -> str:
        """Get private key as string"""
        return self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode()

    def get_public_key_string(self) -> str:
        """Get public key as string"""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()

    def get_address(self) -> str:
        """Generate a proper blockchain address from the public key"""
        # Get the public key in DER format
        public_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        # SHA-256 hash
        sha256_hash = hashlib.sha256(public_bytes).digest()
        
        # RIPEMD-160 hash
        ripemd160 = hashlib.new('ripemd160')
        ripemd160.update(sha256_hash)
        ripemd160_hash = ripemd160.digest()
        
        # Add version byte (0x00 for mainnet)
        version_ripemd160_hash = b'\x00' + ripemd160_hash
        
        # Double SHA-256 for checksum
        double_sha256 = hashlib.sha256(hashlib.sha256(version_ripemd160_hash).digest()).digest()
        
        # First 4 bytes of double SHA-256 as checksum
        checksum = double_sha256[:4]
        
        # Combine version, ripemd160 hash, and checksum
        binary_address = version_ripemd160_hash + checksum
        
        # Base58 encode
        address = base58.b58encode(binary_address).decode()
        
        return address

    @staticmethod
    def create_signature(message: str, private_key: rsa.RSAPrivateKey) -> str:
        """Create a digital signature for a message using a private key"""
        signature = private_key.sign(
            message.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode()

    @staticmethod
    def verify_signature(message: str, signature: str, public_key: rsa.RSAPublicKey) -> bool:
        """Verify a digital signature using a public key"""
        try:
            signature_bytes = base64.b64decode(signature)
            public_key.verify(
                signature_bytes,
                message.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception:
            return False

    def sign_data(self, data: str) -> Optional[str]:
        """Sign arbitrary data using the instance's private key"""
        try:
            return self.create_signature(data, self.private_key)
        except Exception:
            return None

    def verify_data(self, data: str, signature: str) -> bool:
        """Verify signed data using the instance's public key"""
        return self.verify_signature(data, signature, self.public_key)

    def get_public_key(self) -> rsa.RSAPublicKey:
        """Get the public key"""
        return self.public_key