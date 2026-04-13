import os
import subprocess
import sys
from pathlib import Path


def run_command(name, command, shell=False):
    print(f"--- Running {name} ---")
    print(f"Command: {' '.join(command) if isinstance(command, list) else command}")
    try:
        subprocess.run(command, check=True, shell=shell, capture_output=False)
        print(f"--- {name} COMPLETED SUCCESSFULLY ---\n")
        return True
    except subprocess.CalledProcessError as e:
        print(f"!!! {name} FAILED !!! (Exit code: {e.returncode})\n")
        return False


def main():
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    os.environ["PYTHONPATH"] = str(project_root)

    print("========================================")
    print("STARTING BUILD AND VERIFICATION")
    print("========================================")

    # Sequence for a full 'build' in this project:
    # 1. Auto-lint and format (clean up the code)
    # 2. Type checking (ensure consistency)
    # 3. Unit tests with coverage
    # 4. Smoke tests (verify core functionality)

    steps = [
        ("Auto-Linting", [sys.executable, "scripts/auto_lint.py"], False),
        ("Mypy Type Check", [sys.executable, "-m", "mypy"], False),
        (
            "Unit Tests with Coverage",
            [sys.executable, "-m", "pytest", "tests/", "-v", "--cov=."],
            True,
        ),
        ("Smoke Test Suite", [sys.executable, "main.py", "--suite", "smoke"], True),
    ]

    all_passed = True
    failed_steps = []

    for name, cmd, is_shell in steps:
        if not run_command(name, cmd, shell=is_shell):
            all_passed = False
            failed_steps.append(name)
            # We don't stop on non-critical failures if we want a full report
            # But usually build should stop on first failure. Let's decide based on importance.
            if name in ["Unit Tests with Coverage", "Mypy Type Check"]:
                print(f"CRITICAL STEP '{name}' FAILED. Aborting build.")
                break

    print("========================================")
    if all_passed:
        print("BUILD SUCCESSFUL!")
        print("All checks, linting, and tests passed.")
        sys.exit(0)
    else:
        print("BUILD FAILED!")
        print(f"Failed steps: {', '.join(failed_steps)}")
        sys.exit(1)
    print("========================================")


if __name__ == "__main__":
    main()
