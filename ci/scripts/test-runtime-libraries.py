"""Exercise compiled dependencies inside the final runtime image."""
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from psycopg import pq

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
token = jwt.encode({"sub": "runtime-check"}, key, algorithm="RS256")
assert jwt.decode(token, key.public_key(), algorithms=["RS256"])["sub"] == "runtime-check"
assert pq.version() > 0
assert pq.__impl__ == "binary"
print("Native cryptography and bundled libpq checks passed.")
