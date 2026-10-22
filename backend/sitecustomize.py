"""Runtime compatibility shims."""

import sys

try:
    import starlette.exceptions

    if "starlette.deprecation" not in sys.modules:
        sys.modules["starlette.deprecation"] = starlette.exceptions
except Exception:
    pass
