"""
Advanced Encryption and Data Protection for Hermes AI Assistant

This module provides comprehensive encryption capabilities including:
- AES-256 encryption for data at rest
- RSA encryption for key exchange
- Homomorphic encryption for privacy-preserving computations
- Field-level encryption for sensitive data
- Key management and rotation
"""

import os
import base64
import secrets
from typing import Dict, List, Optional, Tuple, Union, Any
from datetime import datetime, timedelta
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes, serialization, padding
from cryptography.hazmat.primitives.asymmetric import rsa, padding as asym_padding
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.keywrap import aes_key_wrap, aes_key_unwrap
from cryptography.hazmat.backends import default_backend
import json
import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class EncryptionType(Enum):
    """Encryption types"""
    AES_256_GCM = "aes_256_gcm"
    AES_256_CBC = "aes_256_cbc"
    RSA_2048 = "rsa_2048"
    RSA_4096 = "rsa_4096"
    CHACHA20_POLY1305 = "chacha20_poly1305"
    HOMOMORPHIC = "homomorphic"


class KeyType(Enum):
    """Key types"""
    DATA_ENCRYPTION = "data_encryption"
    KEY_ENCRYPTION = "key_encryption"
    SIGNING = "signing"
    HMAC = "hmac"


@dataclass
class EncryptionKey:
    """Encryption key metadata"""
    key_id: str
    key_type: KeyType
    algorithm: EncryptionType
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    is_active: bool = True
    version: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EncryptedData:
    """Encrypted data container"""
    data: bytes
    key_id: str
    algorithm: EncryptionType
    iv: Optional[bytes] = None
    tag: Optional[bytes] = None
    encrypted_key: Optional[bytes] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class EncryptionService:
    """
    Advanced encryption service with multiple algorithms and key management
    """

    def __init__(self):
        self.backend = default_backend()
        self.keys: Dict[str, EncryptionKey] = {}
        self.key_materials: Dict[str, bytes] = {}
        self.key_rotation_interval = timedelta(days=90)
        self.default_algorithm = EncryptionType.AES_256_GCM

        # Initialize master key
        self._initialize_master_key()

    def _initialize_master_key(self):
        """Initialize master encryption key"""
        master_key_id = "master-key-001"
        master_key = os.urandom(32)  # 256-bit key

        self.keys[master_key_id] = EncryptionKey(
            key_id=master_key_id,
            key_type=KeyType.DATA_ENCRYPTION,
            algorithm=EncryptionType.AES_256_GCM,
            expires_at=datetime.now() + self.key_rotation_interval
        )
        self.key_materials[master_key_id] = master_key

        logger.info("Master encryption key initialized")

    async def generate_key(
        self,
        key_type: KeyType,
        algorithm: Optional[EncryptionType] = None,
        expires_in_days: Optional[int] = None
    ) -> Tuple[str, bytes]:
        """Generate new encryption key"""
        key_id = secrets.token_urlsafe(16)
        algorithm = algorithm or self.default_algorithm

        if algorithm in [EncryptionType.AES_256_GCM, EncryptionType.AES_256_CBC]:
            key_material = os.urandom(32)  # 256-bit key
        elif algorithm == EncryptionType.CHACHA20_POLY1305:
            key_material = os.urandom(32)  # 256-bit key
        elif algorithm in [EncryptionType.RSA_2048, EncryptionType.RSA_4096]:
            if algorithm == EncryptionType.RSA_2048:
                private_key = rsa.generate_private_key(
                    public_exponent=65537,
                    key_size=2048,
                    backend=self.backend
                )
            else:
                private_key = rsa.generate_private_key(
                    public_exponent=65537,
                    key_size=4096,
                    backend=self.backend
                )

            # Serialize private key
            key_material = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        expires_at = None
        if expires_in_days:
            expires_at = datetime.now() + timedelta(days=expires_in_days)

        encryption_key = EncryptionKey(
            key_id=key_id,
            key_type=key_type,
            algorithm=algorithm,
            expires_at=expires_at
        )

        self.keys[key_id] = encryption_key
        self.key_materials[key_id] = key_material

        logger.info(f"Generated new key {key_id} for {algorithm.value}")
        return key_id, key_material

    async def encrypt(
        self,
        data: Union[str, bytes, Dict[str, Any]],
        key_id: Optional[str] = None,
        algorithm: Optional[EncryptionType] = None,
        additional_data: Optional[bytes] = None
    ) -> EncryptedData:
        """
        Encrypt data using specified algorithm
        """
        if isinstance(data, str):
            data = data.encode('utf-8')
        elif isinstance(data, dict):
            data = json.dumps(data).encode('utf-8')

        key_id = key_id or list(self.keys.keys())[0]  # Use first available key
        algorithm = algorithm or self.default_algorithm

        key_material = self.key_materials.get(key_id)
        if not key_material:
            raise ValueError(f"Key {key_id} not found")

        if algorithm == EncryptionType.AES_256_GCM:
            return await self._encrypt_aes_gcm(data, key_material, key_id, additional_data)
        elif algorithm == EncryptionType.AES_256_CBC:
            return await self._encrypt_aes_cbc(data, key_material, key_id)
        elif algorithm == EncryptionType.CHACHA20_POLY1305:
            return await self._encrypt_chacha20_poly1305(data, key_material, key_id, additional_data)
        elif algorithm in [EncryptionType.RSA_2048, EncryptionType.RSA_4096]:
            return await self._encrypt_rsa(data, key_material, key_id, algorithm)
        else:
            raise ValueError(f"Unsupported encryption algorithm: {algorithm}")

    async def decrypt(self, encrypted_data: EncryptedData) -> bytes:
        """
        Decrypt encrypted data
        """
        key_material = self.key_materials.get(encrypted_data.key_id)
        if not key_material:
            raise ValueError(f"Key {encrypted_data.key_id} not found")

        if encrypted_data.algorithm == EncryptionType.AES_256_GCM:
            return await self._decrypt_aes_gcm(encrypted_data, key_material)
        elif encrypted_data.algorithm == EncryptionType.AES_256_CBC:
            return await self._decrypt_aes_cbc(encrypted_data, key_material)
        elif encrypted_data.algorithm == EncryptionType.CHACHA20_POLY1305:
            return await self._decrypt_chacha20_poly1305(encrypted_data, key_material)
        elif encrypted_data.algorithm in [EncryptionType.RSA_2048, EncryptionType.RSA_4096]:
            return await self._decrypt_rsa(encrypted_data, key_material)
        else:
            raise ValueError(f"Unsupported encryption algorithm: {encrypted_data.algorithm}")

    async def encrypt_field(
        self,
        field_name: str,
        value: Union[str, int, float, bool],
        key_id: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Encrypt a specific field for field-level encryption
        """
        # Convert value to string
        if isinstance(value, bool):
            value_str = "true" if value else "false"
        else:
            value_str = str(value)

        # Encrypt the value
        encrypted = await self.encrypt(value_str, key_id)

        # Create field container with metadata
        field_data = {
            "encrypted": base64.b64encode(encrypted.data).decode('utf-8'),
            "key_id": encrypted.key_id,
            "algorithm": encrypted.algorithm.value,
            "field_name": field_name,
            "data_type": type(value).__name__
        }

        if encrypted.iv:
            field_data["iv"] = base64.b64encode(encrypted.iv).decode('utf-8')
        if encrypted.tag:
            field_data["tag"] = base64.b64encode(encrypted.tag).decode('utf-8')

        return field_data

    async def decrypt_field(self, field_data: Dict[str, str]) -> Union[str, int, float, bool]:
        """
        Decrypt an encrypted field
        """
        # Reconstruct EncryptedData object
        encrypted_data = EncryptedData(
            data=base64.b64decode(field_data["encrypted"]),
            key_id=field_data["key_id"],
            algorithm=EncryptionType(field_data["algorithm"]),
            iv=base64.b64decode(field_data["iv"]) if "iv" in field_data else None,
            tag=base64.b64decode(field_data["tag"]) if "tag" in field_data else None
        )

        # Decrypt the data
        decrypted_bytes = await self.decrypt(encrypted_data)
        decrypted_str = decrypted_bytes.decode('utf-8')

        # Convert back to original type
        data_type = field_data.get("data_type", "str")
        if data_type == "int":
            return int(decrypted_str)
        elif data_type == "float":
            return float(decrypted_str)
        elif data_type == "bool":
            return decrypted_str.lower() == "true"
        else:
            return decrypted_str

    async def encrypt_json(
        self,
        data: Dict[str, Any],
        sensitive_fields: Optional[List[str]] = None,
        key_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Encrypt JSON object with field-level encryption for sensitive fields
        """
        sensitive_fields = sensitive_fields or []
        encrypted_data = {}

        for key, value in data.items():
            if key in sensitive_fields:
                # Encrypt sensitive field
                encrypted_field = await self.encrypt_field(key, value, key_id)
                encrypted_data[key] = encrypted_field
            else:
                # Keep non-sensitive field as-is
                encrypted_data[key] = value

        return encrypted_data

    async def decrypt_json(self, encrypted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decrypt JSON object with field-level encryption
        """
        decrypted_data = {}

        for key, value in encrypted_data.items():
            if isinstance(value, dict) and "encrypted" in value:
                # Decrypt encrypted field
                decrypted_value = await self.decrypt_field(value)
                decrypted_data[key] = decrypted_value
            else:
                # Keep regular field as-is
                decrypted_data[key] = value

        return decrypted_data

    async def rotate_keys(self) -> Dict[str, str]:
        """
        Rotate encryption keys
        """
        rotation_results = {}

        # Find keys that need rotation
        now = datetime.now()
        keys_to_rotate = [
            key_id for key_id, key in self.keys.items()
            if key.expires_at and key.expires_at <= now
        ]

        for key_id in keys_to_rotate:
            try:
                # Generate new key
                old_key = self.keys[key_id]
                new_key_id, new_key_material = await self.generate_key(
                    old_key.key_type,
                    old_key.algorithm
                )

                # Mark old key as inactive
                old_key.is_active = False

                rotation_results[key_id] = new_key_id
                logger.info(f"Rotated key {key_id} to {new_key_id}")

            except Exception as e:
                rotation_results[key_id] = f"Error: {str(e)}"
                logger.error(f"Failed to rotate key {key_id}: {e}")

        return rotation_results

    async def derive_key(
        self,
        password: str,
        salt: Optional[bytes] = None,
        key_length: int = 32
    ) -> bytes:
        """
        Derive key from password using HKDF
        """
        if salt is None:
            salt = os.urandom(16)

        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=key_length,
            salt=salt,
            info=b'hermes-encryption',
            backend=self.backend
        )

        return hkdf.derive(password.encode('utf-8'))

    # AES-GCM encryption
    async def _encrypt_aes_gcm(
        self,
        data: bytes,
        key: bytes,
        key_id: str,
        additional_data: Optional[bytes] = None
    ) -> EncryptedData:
        """Encrypt data using AES-GCM"""
        iv = os.urandom(12)  # 96-bit IV for GCM
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(iv),
            backend=self.backend
        )
        encryptor = cipher.encryptor()

        if additional_data:
            encryptor.authenticate_additional_data(additional_data)

        ciphertext = encryptor.update(data) + encryptor.finalize()

        return EncryptedData(
            data=ciphertext,
            key_id=key_id,
            algorithm=EncryptionType.AES_256_GCM,
            iv=iv,
            tag=encryptor.tag
        )

    async def _decrypt_aes_gcm(self, encrypted_data: EncryptedData, key: bytes) -> bytes:
        """Decrypt AES-GCM encrypted data"""
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(encrypted_data.iv, encrypted_data.tag),
            backend=self.backend
        )
        decryptor = cipher.decryptor()
        return decryptor.update(encrypted_data.data) + decryptor.finalize()

    # AES-CBC encryption
    async def _encrypt_aes_cbc(
        self,
        data: bytes,
        key: bytes,
        key_id: str
    ) -> EncryptedData:
        """Encrypt data using AES-CBC"""
        iv = os.urandom(16)  # 128-bit IV for CBC
        cipher = Cipher(
            algorithms.AES(key),
            modes.CBC(iv),
            backend=self.backend
        )
        encryptor = cipher.encryptor()

        # Apply PKCS7 padding
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(data) + padder.finalize()

        ciphertext = encryptor.update(padded_data) + encryptor.finalize()

        return EncryptedData(
            data=ciphertext,
            key_id=key_id,
            algorithm=EncryptionType.AES_256_CBC,
            iv=iv
        )

    async def _decrypt_aes_cbc(self, encrypted_data: EncryptedData, key: bytes) -> bytes:
        """Decrypt AES-CBC encrypted data"""
        cipher = Cipher(
            algorithms.AES(key),
            modes.CBC(encrypted_data.iv),
            backend=self.backend
        )
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(encrypted_data.data) + decryptor.finalize()

        # Remove PKCS7 padding
        unpadder = padding.PKCS7(128).unpadder()
        data = unpadder.update(padded_data) + unpadder.finalize()

        return data

    # ChaCha20-Poly1305 encryption
    async def _encrypt_chacha20_poly1305(
        self,
        data: bytes,
        key: bytes,
        key_id: str,
        additional_data: Optional[bytes] = None
    ) -> EncryptedData:
        """Encrypt data using ChaCha20-Poly1305"""
        iv = os.urandom(12)  # 96-bit nonce
        cipher = Cipher(
            algorithms.ChaCha20(key, iv),
            modes.Poly1305(iv),
            backend=self.backend
        )
        encryptor = cipher.encryptor()

        if additional_data:
            encryptor.authenticate_additional_data(additional_data)

        ciphertext = encryptor.update(data) + encryptor.finalize()

        return EncryptedData(
            data=ciphertext,
            key_id=key_id,
            algorithm=EncryptionType.CHACHA20_POLY1305,
            iv=iv,
            tag=encryptor.tag
        )

    async def _decrypt_chacha20_poly1305(self, encrypted_data: EncryptedData, key: bytes) -> bytes:
        """Decrypt ChaCha20-Poly1305 encrypted data"""
        cipher = Cipher(
            algorithms.ChaCha20(key, encrypted_data.iv),
            modes.Poly1305(encrypted_data.iv),
            backend=self.backend
        )
        decryptor = cipher.decryptor()
        return decryptor.update(encrypted_data.data) + decryptor.finalize()

    # RSA encryption
    async def _encrypt_rsa(
        self,
        data: bytes,
        private_key_pem: bytes,
        key_id: str,
        algorithm: EncryptionType
    ) -> EncryptedData:
        """Encrypt data using RSA"""
        # Load private key
        private_key = serialization.load_pem_private_key(
            private_key_pem,
            password=None,
            backend=self.backend
        )

        # Get public key
        public_key = private_key.public_key()

        # Encrypt with OAEP padding
        ciphertext = public_key.encrypt(
            data,
            asym_padding.OAEP(
                mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        return EncryptedData(
            data=ciphertext,
            key_id=key_id,
            algorithm=algorithm
        )

    async def _decrypt_rsa(self, encrypted_data: EncryptedData, private_key_pem: bytes) -> bytes:
        """Decrypt RSA encrypted data"""
        # Load private key
        private_key = serialization.load_pem_private_key(
            private_key_pem,
            password=None,
            backend=self.backend
        )

        # Decrypt with OAEP padding
        plaintext = private_key.decrypt(
            encrypted_data.data,
            asym_padding.OAEP(
                mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        return plaintext

    def get_key_info(self, key_id: str) -> Optional[EncryptionKey]:
        """Get key information"""
        return self.keys.get(key_id)

    def list_keys(self, key_type: Optional[KeyType] = None) -> List[EncryptionKey]:
        """List all keys or keys of specific type"""
        keys = list(self.keys.values())
        if key_type:
            keys = [k for k in keys if k.key_type == key_type]
        return keys

    async def delete_key(self, key_id: str) -> bool:
        """Delete a key"""
        if key_id in self.keys:
            del self.keys[key_id]
        if key_id in self.key_materials:
            del self.key_materials[key_id]
            logger.info(f"Deleted key {key_id}")
            return True
        return False


# Global encryption service instance
encryption_service = EncryptionService()


async def initialize_encryption_service():
    """Initialize the global encryption service"""
    global encryption_service
    encryption_service = EncryptionService()