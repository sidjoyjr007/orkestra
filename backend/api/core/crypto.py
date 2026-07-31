from cryptography.fernet import Fernet
from backend.api.core.config import settings

# Initialize Fernet cipher suite
_cipher_suite = Fernet(settings.ENCRYPTION_KEY.encode('utf-8'))

def encrypt_secret(secret_value: str) -> str:
    """Encrypts a plaintext string and returns a base64 encoded string."""
    return _cipher_suite.encrypt(secret_value.encode('utf-8')).decode('utf-8')

def decrypt_secret(encrypted_value: str) -> str:
    """Decrypts a base64 encoded string back to plaintext."""
    return _cipher_suite.decrypt(encrypted_value.encode('utf-8')).decode('utf-8')
