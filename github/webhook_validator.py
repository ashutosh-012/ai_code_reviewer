import hmac
import hashlib

def verify(body: bytes, secret: str, header: str) -> bool:
    if not header:
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, header)