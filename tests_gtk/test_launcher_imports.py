"""The launcher's calculator (numpy) and unit converter (requests) load on
first use, not with the shell: ~0.08 s of every start."""

import os
import subprocess
import sys


def test_launcher_import_skips_calculator_and_converter(sandbox):
    code = (
        "import sys, modules.launcher; "
        "print(sorted(m for m in ('utils.calculator', 'utils.conversion', 'numpy', 'requests') "
        "if m in sys.modules))"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                            env=os.environ, timeout=60)
    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.strip().splitlines()[-1] == "[]"
