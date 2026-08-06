"""Run the whole Python suite: python tests/run_all.py

Modules run in separate processes so environment mutations and module-level
app state can't bleed between them. (pytest tests/ works too.)
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

MODULES = [
    "test_ish_library.py",
    "test_core_routes.py",
    "test_tickets_api.py",
    "test_vercel_entrypoint.py",
]

failures = 0
for module in MODULES:
    print("=" * 60)
    print(module)
    print("=" * 60)
    result = subprocess.run([sys.executable, os.path.join(HERE, module)],
                            cwd=HERE)
    if result.returncode != 0:
        failures += 1

print("=" * 60)
print("SUITE:", "PASS" if failures == 0 else "%d module(s) failed" % failures)
sys.exit(1 if failures else 0)
