"""
Password Provider for DI using cryptography (PBKDF2HMAC) with embedded salt.
"""
import base64
import hmac
import re
import secrets

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class PasswordProvider:
    """
    Password Provider for hashing and verification using PBKDF2HMAC KDF.
    Stored hash format:
    - Fixed-length (512 chars) urlsafe base64 token, prefixed with algorithm:
      pbkdf2_sha256$<512-char base64url payload>
      where payload = [version:1][iterations:4][salt:128][dk:240]
    """

    def __init__(self):
        """
        Initialize the PasswordProvider with the default parameters.
        """
        self._PASSWORD_MIN_LENGTH = 8
        # PBKDF2 parameters (moderate defaults)
        self.__PBKDF2_ITERATIONS = 300000
        self.__HASH_ALGORITHM = hashes.SHA512()
        self.__SALT_NUM_BYTES = 128  # 128 bytes salt
        self.__FORMAT_VERSION = 1
        # For fixed-length total string of 512 including prefix 'pbkdf2_sha256$' (14 chars):
        # We need base64url payload length = 498 (no padding). Choose payload bytes n=373 (n % 3 == 1)
        # Padded base64 length = 500, padding '==' stripped -> 498.
        self.__FIXED_PAYLOAD_TOTAL_BYTES = 373
        # payload = [version:1][iterations:4][salt:self.__SALT_NUM_BYTES][dk:derived_len]
        self.__FIXED_DERIVED_KEY_LENGTH = self.__FIXED_PAYLOAD_TOTAL_BYTES - (1 + 4 + self.__SALT_NUM_BYTES)  # 240 bytes

    def validate_password(self, password: str) -> bool:
        """
        Validate password
        :param password:
        :return:
        """
        errors = []
        if len(password) < self._PASSWORD_MIN_LENGTH:
            errors.append(f"密碼長度應至少為 8 個字元。")

        if not re.search(r"[a-z]", password):
            errors.append("請至少包含一個小寫字母。")
        if not re.search(r"[A-Z]", password):
            errors.append("請至少包含一個大寫字母。")
        if not re.search(r"\d", password):
            errors.append("請至少包含一個數字。")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-\\\[\]/~`+=]", password):
            errors.append("請至少包含一個特殊字元 (如 !@#$%^&* 等)。")

        is_valid = (len(errors) == 0)
        return is_valid


    def _generate_salt_bytes(self) -> bytes:
        """Generate random salt bytes."""
        return secrets.token_bytes(self.__SALT_NUM_BYTES)

    def _derive_key(self, password: str, salt_bytes: bytes) -> bytes:
        """
        Derive key bytes using PBKDF2HMAC for a given password and salt bytes.
        :param password:
        :param salt_bytes:
        :return:
        """
        kdf = PBKDF2HMAC(
            algorithm=self.__HASH_ALGORITHM,
            length=self.__FIXED_DERIVED_KEY_LENGTH,
            salt=salt_bytes,
            iterations=self.__PBKDF2_ITERATIONS,
        )
        return kdf.derive(password.encode("utf-8"))

    def _build_payload(self, salt_bytes: bytes, derived_key: bytes) -> bytes:
        """
        Build payload bytes: [version:1][iterations:4 big-endian][salt:128][dk:240]
        :param salt_bytes:
        :param derived_key:
        :return:
        """
        version_byte = self.__FORMAT_VERSION.to_bytes(1, "big")
        iter_bytes = self.__PBKDF2_ITERATIONS.to_bytes(4, "big")
        return version_byte + iter_bytes + salt_bytes + derived_key

    def hash_password(self, password: str) -> str:
        """
        Hash password with PBKDF2HMAC and embed salt and iterations in a 512-char token.
        :param password: Plaintext password
        :return: 'pbkdf2_sha256$' + 512-char urlsafe base64 string (embedded salt and iterations)
        """
        salt_bytes = self._generate_salt_bytes()
        derived_key = self._derive_key(password=password, salt_bytes=salt_bytes)
        payload = self._build_payload(salt_bytes=salt_bytes, derived_key=derived_key)
        token = base64.urlsafe_b64encode(payload).decode("utf-8").rstrip("=")
        return f"pbkdf2_sha256${token}"

    def verify_password(self, password: str, password_hash: str) -> bool:
        """
        Verify password against embedded-salt hash using PBKDF2HMAC.
        :param password: Plaintext password
        :param password_hash: Stored hash string ('pbkdf2_sha256$' + fixed-length token)
        :return: True if matches, False otherwise
        """
        try:
            if not password_hash.startswith("pbkdf2_sha256$"):
                return False
            token = password_hash.split("$", 1)[1]
            # Fixed-length token
            # re-pad token for base64 decoding
            padded_token = token + ("=" * (-len(token) % 4))
            payload = base64.urlsafe_b64decode(padded_token.encode("utf-8"))
            if len(payload) != self.__FIXED_PAYLOAD_TOTAL_BYTES:
                return False
            version = payload[0]
            if version != self.__FORMAT_VERSION:
                return False
            iterations = int.from_bytes(payload[1:5], "big")
            salt_bytes = payload[5:5 + self.__SALT_NUM_BYTES]
            expected_key = payload[5 + self.__SALT_NUM_BYTES:]
            # Derive key with same length as expected
            kdf = PBKDF2HMAC(
                algorithm=self.__HASH_ALGORITHM,
                length=len(expected_key),
                salt=salt_bytes,
                iterations=iterations,
            )
            derived_key = kdf.derive(password.encode("utf-8"))
            return hmac.compare_digest(derived_key, expected_key)
        except Exception:
            return False
