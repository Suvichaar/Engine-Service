"""Generate a bcrypt hash for ADMIN_PASSWORD_HASH.

Usage:
    python scripts/hash_password.py 'my-secret-password'

Prints the bcrypt hash to stdout. Paste it into your Azure App Service
configuration as the ADMIN_PASSWORD_HASH environment variable.
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

# Make `app.*` importable when this script is run directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.auth import hash_password  # noqa: E402


def main() -> int:
    if len(sys.argv) > 1:
        password = sys.argv[1]
    else:
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm: ")
        if password != confirm:
            print("Passwords do not match.", file=sys.stderr)
            return 1

    if not password:
        print("Password cannot be empty.", file=sys.stderr)
        return 1

    print(hash_password(password))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
