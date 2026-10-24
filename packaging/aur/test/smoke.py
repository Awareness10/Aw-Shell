"""Start the installed /usr/bin/aw-shell inside the tests_gtk sandbox
(headless sway, private D-Bus, fake Hyprland, temporary HOME) and check that it
keeps running without a Python traceback. Run by run.sh in the Arch container,
so it uses Arch's real Python packages and the package's bundled libraries."""

import os
import signal
import subprocess
import sys
import time

sys.path.insert(0, "/src/tests_gtk")
import conftest  # noqa: E402  (sets up the sandbox on import)

RUN_SECONDS = 15

sandbox = conftest.SANDBOX
log_path = sandbox.root / "aw-shell.log"
# First start: no config yet, so the shell opens the (Qt) settings window too
env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
with open(log_path, "w") as log:
    proc = subprocess.Popen(["/usr/bin/aw-shell"], env=env, stdout=log, stderr=subprocess.STDOUT,
                            start_new_session=True)
    time.sleep(RUN_SECONDS)
    alive = proc.poll() is None
    if alive:
        os.killpg(proc.pid, signal.SIGTERM)  # the shell and what it started
        proc.wait(timeout=10)

output = log_path.read_text()
print(output[-4000:])
problems = []
if not alive:
    problems.append(f"aw-shell exited after less than {RUN_SECONDS}s (code {proc.returncode})")
if "Traceback" in output:
    problems.append("Python traceback in aw-shell's output")
for problem in problems:
    print(f"FAIL: {problem}")
if not problems:
    print(f"OK: aw-shell ran for {RUN_SECONDS}s without errors")
sys.exit(1 if problems else 0)
