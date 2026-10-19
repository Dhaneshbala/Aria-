"""Make `gateway` importable for pytest runs from anywhere in the repo.

deploy/gateway/tests/conftest.py → parents[2] is deploy/, so
`import gateway.main` resolves against deploy/gateway/.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
