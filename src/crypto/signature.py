#src/crypto/signature.py
from typing import Optional
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
import base64

class SignatureManager:
    """
    Handles digital signatures for transactions
    """
    
    @staticmethod
    def create_signature(message: str, private_key: rsa.RSAPrivateKey) -> str:
        """
        Create a digital signature for a message using a private key
        """
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
        """
        Verify a digital signature using a public key
        """
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

    @staticmethod
    def sign_data(data: str, private_key: rsa.RSAPrivateKey) -> Optional[str]:
        """
        Sign arbitrary data, returns None if signing fails
        """
        try:
            return SignatureManager.create_signature(data, private_key)
        except Exception:
            return None

    @staticmethod
    def verify_data(data: str, signature: str, public_key: rsa.RSAPublicKey) -> bool:
        """
        Verify signed data
        """
        return SignatureManager.verify_signature(data, signature, public_key)