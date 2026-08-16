"""Phase 8 exit verification — Arabic chrome + scoped RTL/LTR boundaries (issues #145-#146).

Runs the static-analysis checks from tests/test_phase8_exit.py standalone
(mirrors the phase 6/7 exit-script convention: `python scripts/verify_phase8_exit.py`).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from test_phase8_exit import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
