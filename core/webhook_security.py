import hashlib
import hmac


def sign_payload(secret: str, body: bytes) -> str:
    # HMAC-SHA256 over the RAW request bytes (not a re-serialized JSON: one
    # different space or key order would change the signature). Only someone
    # who knows the shared secret can produce a valid value.
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def verify_signature(secret: str, body: bytes, signature: str | None) -> bool:
    if not signature:
        return False
    expected = sign_payload(secret, body)
    # compare_digest takes the same time no matter where the strings first
    # differ, so an attacker can't guess the signature byte by byte from
    # response times. Compared as bytes: str with non-ASCII characters would
    # raise TypeError instead of returning False.
    return hmac.compare_digest(expected.encode(), signature.encode())