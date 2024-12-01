import base64
import logging

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

logger = logging.getLogger(__name__)

class CryptoManager:
    def __init__(self):
        self.key = Fernet.generate_key()
        self.cipher_suite = Fernet(self.key)

    def encrypt(self, data: str) -> str:
        try:
            return self.cipher_suite.encrypt(data.encode()).decode()
        except Exception as e:
            logger.error(f"Encryption failed: {str(e)}")
            raise

    def decrypt(self, encrypted_data: str) -> str:
        try:
            return self.cipher_suite.decrypt(encrypted_data.encode()).decode()
        except Exception as e:
            logger.error(f"Decryption failed: {str(e)}")
            raise

    def generate_key_pair(self):
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        return private_key, private_key.public_key()