"""Bootstrap the first superadmin (Section 13C).

The initial administrator exists ONLY through this verified command-line
path — never through any API input, URL tweak or frontend state change:

    cd backend && ../.venv/bin/python -m tools.superadmin <username>

It prompts for the password (hidden, 10+ chars, letters+digits),
creates or promotes the account, and is idempotent (safe re-runs).

Run on the server itself (loopback), never remotely.
"""

from __future__ import annotations

import getpass
import sys

sys.path.insert(0, ".")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    username = sys.argv[1].strip().lower()
    from services import accounts, audit

    accounts._init_schema()
    msg = accounts.validate_username(username)
    if msg:
        print(f"Invalid username: {msg}")
        return 2
    for _ in range(3):
        password = getpass.getpass(
            f"Password for '{username}' (10+ chars, letters+digits): "
        )
        problem = accounts.validate_password(password)
        if not problem:
            break
        print(f"  Weak password: {problem}")
    else:
        print("Too many weak attempts — aborted.")
        return 2
    user = accounts.bootstrap_superadmin(username, password)
    audit.log(
        user["id"],
        username,
        "superadmin_bootstrap",
        target=f"user:{user['id']}",
        outcome="ok",
    )
    print(f"OK: '{username}' is a superadmin (id={user['id']}, role={user['role']}).")
    print("Next: set ARIA_AUTH_MODE=accounts to require sign-in.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
