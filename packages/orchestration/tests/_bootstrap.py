"""Make the package importable for direct unittest discovery."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

# A host may expose its temporary directory through a standard filesystem alias.
# Keep fixtures on the equivalent physical base so tests exercise only the
# symlinks they create explicitly.
tempfile.tempdir = str(Path(tempfile.gettempdir()).resolve(strict=True))
