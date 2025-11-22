"""Quick script to check if all dependencies are installed."""

import sys

def check_import(module_name, package_name=None):
    """Check if a module can be imported."""
    try:
        __import__(module_name)
        print(f"[OK] {package_name or module_name} is installed")
        return True
    except ImportError as e:
        print(f"[MISSING] {package_name or module_name} is NOT installed")
        print(f"   Error: {e}")
        print(f"   Install with: pip install {package_name or module_name}")
        return False

print("=" * 60)
print("Checking Dependencies for URL Extraction")
print("=" * 60)
print()

checks = [
    ("newspaper", "newspaper3k"),
    ("PIL", "pillow"),
    ("httpx", "httpx"),
    ("boto3", "boto3"),
    ("fastapi", "fastapi"),
    ("pydantic", "pydantic"),
]

all_ok = True
for module, package in checks:
    if not check_import(module, package):
        all_ok = False

print()
print("=" * 60)
if all_ok:
    print("✅ All dependencies are installed!")
else:
    print("❌ Some dependencies are missing!")
    print("   Please install missing packages and try again.")
print("=" * 60)

sys.exit(0 if all_ok else 1)

