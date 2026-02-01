from passlib.context import CryptContext
import bcrypt

try:
    print(f"Bcrypt version: {bcrypt.__version__}")
except:
    print("Could not read bcrypt version directly")

try:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hash = pwd_context.hash("test_password")
    print(f"Hash success: {hash}")
    print("Verification success")
except Exception as e:
    print(f"Error: {e}")
