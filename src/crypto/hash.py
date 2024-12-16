# src/crypto/hash.py
from typing import Union
import hashlib
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import base64

class Hash:
    @staticmethod
    def hash_public_key(public_key: Union[str, bytes, rsa.RSAPublicKey]) -> str:
        """
        Create hash of a public key
        """
        if isinstance(public_key, rsa.RSAPublicKey):
            # Convert RSA public key to bytes
            public_key = public_key.public_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
        elif isinstance(public_key, str):
            public_key = public_key.encode()
        
        # First SHA-256
        sha256_hash = hashlib.sha256(public_key).digest()
        # Then RIPEMD-160
        ripemd160_hash = hashlib.new('ripemd160')
        ripemd160_hash.update(sha256_hash)
        
        return ripemd160_hash.hexdigest()

    @staticmethod
    def hash_string(data: str) -> str:
        """
        Create SHA-256 hash of a string
        """
        return hashlib.sha256(data.encode()).hexdigest()