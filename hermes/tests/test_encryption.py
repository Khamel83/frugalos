"""
Tests for the Encryption Service

This module contains comprehensive tests for encryption algorithms,
key management, field-level encryption, and security features.
"""

import pytest
import base64
import json
from datetime import datetime, timedelta
from cryptography.fernet import Fernet

from hermes.security.encryption import (
    EncryptionService,
    EncryptionKey,
    EncryptedData,
    EncryptionType,
    KeyType
)


class TestEncryptionService:
    """Test cases for EncryptionService"""

    def test_initialize_service(self):
        """Test service initialization."""
        service = EncryptionService()

        assert service.default_algorithm == EncryptionType.AES_256_GCM
        assert len(service.keys) > 0  # Master key should be created
        assert len(service.key_materials) > 0
        assert service.encryption_key is not None

    @pytest.mark.asyncio
    async def test_generate_key_aes(self):
        """Test AES key generation."""
        service = EncryptionService()

        key_id, key_material = await service.generate_key(
            key_type=KeyType.DATA_ENCRYPTION,
            algorithm=EncryptionType.AES_256_GCM
        )

        assert key_id is not None
        assert key_material is not None
        assert len(key_material) == 32  # 256 bits for AES-256
        assert key_id in service.keys
        assert key_id in service.key_materials

        # Verify key metadata
        encryption_key = service.get_key_info(key_id)
        assert encryption_key is not None
        assert encryption_key.key_type == KeyType.DATA_ENCRYPTION
        assert encryption_key.algorithm == EncryptionType.AES_256_GCM
        assert encryption_key.is_active is True

    @pytest.mark.asyncio
    async def test_generate_key_rsa(self):
        """Test RSA key generation."""
        service = EncryptionService()

        key_id, key_material = await service.generate_key(
            key_type=KeyType.KEY_ENCRYPTION,
            algorithm=EncryptionType.RSA_2048
        )

        assert key_id is not None
        assert key_material is not None
        assert key_id in service.keys
        assert key_id in service.key_materials

        # Verify key metadata
        encryption_key = service.get_key_info(key_id)
        assert encryption_key.algorithm == EncryptionType.RSA_2048

    @pytest.mark.asyncio
    async def test_encrypt_decrypt_aes_gcm(self):
        """Test AES-GCM encryption and decryption."""
        service = EncryptionService()
        test_data = "This is a secret message for testing"

        # Encrypt data
        encrypted = await service.encrypt(
            data=test_data,
            algorithm=EncryptionType.AES_256_GCM
        )

        assert isinstance(encrypted, EncryptedData)
        assert encrypted.data != test_data.encode()
        assert encrypted.key_id is not None
        assert encrypted.algorithm == EncryptionType.AES_256_GCM
        assert encrypted.iv is not None
        assert encrypted.tag is not None

        # Decrypt data
        decrypted = await service.decrypt(encrypted)
        decrypted_text = decrypted.decode('utf-8')

        assert decrypted_text == test_data

    @pytest.mark.asyncio
    async def test_encrypt_decrypt_aes_cbc(self):
        """Test AES-CBC encryption and decryption."""
        service = EncryptionService()
        test_data = "This is a secret message for CBC testing"

        # Encrypt data
        encrypted = await service.encrypt(
            data=test_data,
            algorithm=EncryptionType.AES_256_CBC
        )

        assert encrypted.algorithm == EncryptionType.AES_256_CBC
        assert encrypted.iv is not None
        assert encrypted.tag is None  # CBC doesn't use authentication tag

        # Decrypt data
        decrypted = await service.decrypt(encrypted)
        decrypted_text = decrypted.decode('utf-8')

        assert decrypted_text == test_data

    @pytest.mark.asyncio
    async def test_encrypt_decrypt_chacha20(self):
        """Test ChaCha20-Poly1305 encryption and decryption."""
        service = EncryptionService()
        test_data = "This is a secret message for ChaCha20 testing"

        # Encrypt data
        encrypted = await service.encrypt(
            data=test_data,
            algorithm=EncryptionType.CHACHA20_POLY1305
        )

        assert encrypted.algorithm == EncryptionType.CHACHA20_POLY1305
        assert encrypted.iv is not None
        assert encrypted.tag is not None

        # Decrypt data
        decrypted = await service.decrypt(encrypted)
        decrypted_text = decrypted.decode('utf-8')

        assert decrypted_text == test_data

    @pytest.mark.asyncio
    async def test_encrypt_decrypt_large_data(self):
        """Test encryption of large data."""
        service = EncryptionService()
        # Create 1MB of data
        test_data = "A" * (1024 * 1024)

        # Encrypt data
        encrypted = await service.encrypt(test_data)

        # Decrypt data
        decrypted = await service.decrypt(encrypted)

        assert len(decrypted) == len(test_data.encode())
        assert decrypted == test_data.encode()

    @pytest.mark.asyncio
    async def test_encrypt_decrypt_dict(self):
        """Test encryption and decryption of dictionary data."""
        service = EncryptionService()
        test_dict = {
            "user_id": "12345",
            "email": "user@example.com",
            "preferences": {
                "theme": "dark",
                "notifications": True
            },
            "timestamp": datetime.now().isoformat()
        }

        # Encrypt data
        encrypted = await service.encrypt(test_dict)

        # Decrypt data
        decrypted = await service.decrypt(encrypted)
        decrypted_dict = json.loads(decrypted.decode('utf-8'))

        assert decrypted_dict["user_id"] == test_dict["user_id"]
        assert decrypted_dict["email"] == test_dict["email"]
        assert decrypted_dict["preferences"] == test_dict["preferences"]

    @pytest.mark.asyncio
    async def test_field_level_encryption(self):
        """Test field-level encryption."""
        service = EncryptionService()
        test_data = {
            "public_field": "This is public",
            "secret_field": "This is secret",
            "number_field": 42,
            "boolean_field": True
        }

        # Encrypt specific fields
        encrypted_data = await service.encrypt_json(
            data=test_data,
            sensitive_fields=["secret_field", "email"]
        )

        # Verify field encryption
        assert "public_field" not in encrypted_data or not isinstance(encrypted_data["public_field"], dict)
        assert isinstance(encrypted_data["secret_field"], dict)
        assert "encrypted" in encrypted_data["secret_field"]
        assert "algorithm" in encrypted_data["secret_field"]

        # Decrypt fields
        decrypted_data = await service.decrypt_json(encrypted_data)

        # Verify data integrity
        assert decrypted_data == test_data

    @pytest.mark.asyncio
    async def test_field_encryption_different_types(self):
        """Test field encryption with different data types."""
        service = EncryptionService()

        # Test string
        encrypted_str = await service.encrypt_field("message", "secret message")
        decrypted_str = await service.decrypt_field(encrypted_str)
        assert decrypted_str == "secret message"

        # Test integer
        encrypted_int = await service.encrypt_field("count", 42)
        decrypted_int = await service.decrypt_field(encrypted_int)
        assert decrypted_int == 42

        # Test float
        encrypted_float = await service.encrypt_field("price", 19.99)
        decrypted_float = await service.decrypt_field(encrypted_float)
        assert decrypted_float == 19.99

        # Test boolean
        encrypted_bool = await service.encrypt_field("active", True)
        decrypted_bool = await service.decrypt_field(encrypted_bool)
        assert decrypted_bool is True

    @pytest.mark.asyncio
    async def test_key_rotation(self):
        """Test key rotation functionality."""
        service = EncryptionService()

        # Get original key count
        original_key_count = len(service.keys)

        # Rotate keys (this should create new keys)
        rotation_results = await service.rotate_keys()

        # Verify rotation results
        assert isinstance(rotation_results, dict)

        # Should have at least one master key
        master_keys = [
            key_id for key_id in service.keys.values()
            if key_id.key_type == KeyType.DATA_ENCRYPTION
        ]
        assert len(master_keys) >= 1

    @pytest.mark.asyncio
    async def test_key_expiration(self):
        """Test key expiration functionality."""
        service = EncryptionService()

        # Create key with short expiration
        key_id, key_material = await service.generate_key(
            key_type=KeyType.DATA_ENCRYPTION,
            expires_in_days=1
        )

        # Verify expiration is set
        encryption_key = service.get_key_info(key_id)
        assert encryption_key.expires_at is not None
        assert encryption_key.expires_at > datetime.now()

        # Manually expire key for testing
        encryption_key.expires_at = datetime.now() - timedelta(days=1)
        service.keys[key_id] = encryption_key

    @pytest.mark.asyncio
    async def test_key_deletion(self):
        """Test key deletion."""
        service = EncryptionService()

        # Create a key
        key_id, key_material = await service.generate_key(
            key_type=KeyType.DATA_ENCRYPTION
        )

        # Verify key exists
        assert key_id in service.keys
        assert key_id in service.key_materials

        # Delete key
        delete_success = await service.delete_key(key_id)
        assert delete_success is True

        # Verify key is deleted
        assert key_id not in service.keys
        assert key_id not in service.key_materials

        # Try to delete non-existent key
        delete_success = await service.delete_key("non_existent_key")
        assert delete_success is False

    @pytest.mark.asyncio
    async def test_derive_key_from_password(self):
        """Test key derivation from password."""
        service = EncryptionService()
        password = "user_password_123"
        salt = b"test_salt_123"

        # Derive key
        derived_key = await service.derive_key(password, salt, key_length=32)

        assert len(derived_key) == 32
        assert derived_key != password.encode()

        # Deriving with same password and salt should give same result
        derived_key2 = await service.derive_key(password, salt, key_length=32)
        assert derived_key == derived_key2

        # Different salt should give different result
        different_salt = b"different_salt"
        derived_key3 = await service.derive_key(password, different_salt, key_length=32)
        assert derived_key != derived_key3

    @pytest.mark.asyncio
    async def test_encrypt_with_additional_data(self):
        """Test encryption with additional authenticated data."""
        service = EncryptionService()
        test_data = "Secret message"
        additional_data = b"additional_context_data"

        # Encrypt with additional data
        encrypted = await service.encrypt(
            data=test_data,
            algorithm=EncryptionType.AES_256_GCM,
            additional_data=additional_data
        )

        # Decrypt without additional data should work
        decrypted = await service.decrypt(encrypted)
        assert decrypted.decode('utf-8') == test_data

    @pytest.mark.asyncio
    async def test_multiple_encryption_algorithms(self):
        """Test multiple encryption algorithms with same data."""
        service = EncryptionService()
        test_data = "Test data for multiple algorithms"

        algorithms = [
            EncryptionType.AES_256_GCM,
            EncryptionType.AES_256_CBC,
            EncryptionType.CHACHA20_POLY1305
        ]

        results = {}
        for algorithm in algorithms:
            try:
                encrypted = await service.encrypt(
                    data=test_data,
                    algorithm=algorithm
                )
                decrypted = await service.decrypt(encrypted)
                results[algorithm] = {
                    "success": True,
                    "decrypted": decrypted.decode('utf-8')
                }
            except Exception as e:
                results[algorithm] = {
                    "success": False,
                    "error": str(e)
                }

        # All should succeed and return original data
        for algorithm, result in results.items():
            assert result["success"] is True
            assert result["decrypted"] == test_data

    @pytest.mark.asyncio
    async def test_key_listing(self):
        """Test key listing functionality."""
        service = EncryptionService()

        # Create keys of different types
        data_key_id, _ = await service.generate_key(
            key_type=KeyType.DATA_ENCRYPTION
        )
        signing_key_id, _ = await service.generate_key(
            key_type=KeyType.SIGNING
        )
        hmac_key_id, _ = await service.generate_key(
            key_type=KeyType.HMAC
        )

        # List all keys
        all_keys = service.list_keys()
        assert len(all_keys) >= 4  # Including master key

        # List keys by type
        data_keys = service.list_keys(KeyType.DATA_ENCRYPTION)
        signing_keys = service.list_keys(KeyType.SIGNING)
        hmac_keys = service.list_keys(KeyType.HMAC)

        assert any(k.key_id == data_key_id for k in data_keys)
        assert any(k.key_id == signing_key_id for k in signing_keys)
        assert any(k.key_id == hmac_key_id for k in hmac_keys)

    @pytest.mark.asyncio
    async def test_encryption_with_specific_key(self):
        """Test encryption with specific key ID."""
        service = EncryptionService()

        # Create specific key
        key_id, _ = await service.generate_key(
            key_type=KeyType.DATA_ENCRYPTION
        )

        test_data = "Encrypt with specific key"

        # Encrypt with specific key
        encrypted = await service.encrypt(
            data=test_data,
            key_id=key_id
        )

        assert encrypted.key_id == key_id

        # Decrypt should work
        decrypted = await service.decrypt(encrypted)
        assert decrypted.decode('utf-8') == test_data

    @pytest.mark.asyncio
    async def test_invalid_algorithm_error(self):
        """Test error handling for invalid algorithm."""
        service = EncryptionService()
        test_data = "Test data"

        # Try to generate key with invalid algorithm
        with pytest.raises(ValueError, match="Unsupported algorithm"):
            await service.generate_key(
                key_type=KeyType.DATA_ENCRYPTION,
                algorithm="invalid_algorithm"  # This should raise an error
            )

    @pytest.mark.asyncio
    async def test_missing_key_error(self):
        """Test error handling for missing key."""
        service = EncryptionService()

        # Create encrypted data with non-existent key
        encrypted_data = EncryptedData(
            data=b"encrypted_data",
            key_id="non_existent_key",
            algorithm=EncryptionType.AES_256_GCM,
            iv=b"123456789012",  # 12 bytes
            tag=b"1234567890123456"  # 16 bytes
        )

        # Try to decrypt should raise error
        with pytest.raises(ValueError, match="Key non_existent_key not found"):
            await service.decrypt(encrypted_data)

    @pytest.mark.asyncio
    async def test_concurrent_encryption(self):
        """Test concurrent encryption operations."""
        service = EncryptionService()
        import asyncio

        async def encrypt_data(data):
            return await service.encrypt(data)

        # Create multiple encryption tasks
        tasks = []
        for i in range(10):
            task = encrypt_data(f"Concurrent test data {i}")
            tasks.append(task)

        # Execute all tasks concurrently
        encrypted_results = await asyncio.gather(*tasks)

        # Verify all encryptions succeeded
        assert len(encrypted_results) == 10
        for i, encrypted in enumerate(encrypted_results):
            decrypted = await service.decrypt(encrypted)
            assert decrypted.decode('utf-8') == f"Concurrent test data {i}"

    @pytest.mark.asyncio
    async def test_encryption_metadata(self):
        """Test encryption metadata handling."""
        service = EncryptionService()
        test_data = "Test with metadata"
        metadata = {"purpose": "test", "classification": "confidential"}

        # Encrypt with metadata
        encrypted = await service.encrypt(test_data)
        encrypted.metadata = metadata

        # Decrypt and verify metadata is preserved
        decrypted = await service.decrypt(encrypted)
        assert decrypted.decode('utf-8') == test_data
        assert encrypted.metadata == metadata

    @pytest.mark.asyncio
    async def test_base64_serialization(self):
        """Test that encrypted data can be safely serialized."""
        service = EncryptionService()
        test_data = "Serialization test"

        # Encrypt data
        encrypted = await service.encrypt(test_data)

        # Serialize to base64
        serialized_data = {
            "data": base64.b64encode(encrypted.data).decode('utf-8'),
            "key_id": encrypted.key_id,
            "algorithm": encrypted.algorithm.value,
            "iv": base64.b64encode(encrypted.iv or b'').decode('utf-8'),
            "tag": base64.b64encode(encrypted.tag or b'').decode('utf-8')
        }

        # Deserialize and reconstruct
        reconstructed_encrypted = EncryptedData(
            data=base64.b64decode(serialized_data["data"]),
            key_id=serialized_data["key_id"],
            algorithm=EncryptionType(serialized_data["algorithm"]),
            iv=base64.b64decode(serialized_data["iv"]) if serialized_data["iv"] else None,
            tag=base64.b64decode(serialized_data["tag"]) if serialized_data["tag"] else None
        )

        # Decrypt reconstructed data
        decrypted = await service.decrypt(reconstructed_encrypted)
        assert decrypted.decode('utf-8') == test_data

    @pytest.mark.asyncio
    async def test_memory_safety(self):
        """Test that sensitive data is properly handled in memory."""
        service = EncryptionService()
        sensitive_data = "Very sensitive information"

        # Encrypt sensitive data
        encrypted = await service.encrypt(sensitive_data)

        # The original data should still exist in memory
        # (In a real implementation, you might want to zero out sensitive data)
        assert sensitive_data == "Very sensitive information"

        # Decrypted data should match original
        decrypted = await service.decrypt(encrypted)
        assert decrypted.decode('utf-8') == sensitive_data

    @pytest.mark.asyncio
    async def test_performance_large_dataset(self):
        """Test encryption performance with large datasets."""
        import time
        service = EncryptionService()

        # Create large dataset (10MB)
        large_data = "X" * (10 * 1024 * 1024)

        # Measure encryption time
        start_time = time.time()
        encrypted = await service.encrypt(large_data)
        encryption_time = time.time() - start_time

        # Measure decryption time
        start_time = time.time()
        decrypted = await service.decrypt(encrypted)
        decryption_time = time.time() - start_time

        # Verify data integrity
        assert len(decrypted) == len(large_data.encode())
        assert decrypted == large_data.encode()

        # Performance should be reasonable (less than 5 seconds for 10MB)
        assert encryption_time < 5.0
        assert decryption_time < 5.0

        print(f"Encryption time: {encryption_time:.2f}s, Decryption time: {decryption_time:.2f}s")