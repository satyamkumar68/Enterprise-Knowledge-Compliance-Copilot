
import base64
import hashlib
import hmac
import secrets


SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
KEY_LENGTH = 64


def hash_password(password: str) -> str:
    """Hash a password using scrypt and a unique random salt."""
    if not isinstance(password, str) or len(password) < 12:
        raise ValueError("Password must contain at least 12 characters.")

    salt = secrets.token_bytes(16)
    derived_key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=KEY_LENGTH,
    )

    encode = lambda value: base64.urlsafe_b64encode(value).decode("ascii")

    return (
        f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}"
        f"${encode(salt)}${encode(derived_key)}"
    )


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password without storing or comparing plaintext passwords."""
    try:
        algorithm, n, r, p, salt_text, key_text = stored_hash.split("$")

        if algorithm != "scrypt":
            return False

        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected_key = base64.urlsafe_b64decode(key_text.encode("ascii"))

        actual_key = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected_key),
        )

        return hmac.compare_digest(actual_key, expected_key)
    except (ValueError, TypeError, UnicodeError):
        return False
