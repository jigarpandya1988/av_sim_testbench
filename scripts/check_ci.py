import os
import subprocess
import sys
from pathlib import Path


def run_step(name, command, shell=False):
    print(f"--- Running {name} ---")
    print(f"Command: {command}")
    try:
        # On Windows, we need shell=True for some commands or use subprocess.run properly
        subprocess.run(command, shell=shell, check=True, capture_output=False)
        print(f"--- {name} PASSED ---\n")
        return True
    except subprocess.CalledProcessError as e:
        print(f"!!! {name} FAILED !!! (Exit code: {e.returncode})\n")
        return False


def main():
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    # Set PYTHONPATH to include project root (mirroring CI)
    os.environ["PYTHONPATH"] = str(project_root)

    steps = [
        ("Ruff Lint", [sys.executable, "-m", "ruff", "check", "."], True),
        ("Ruff Format Check", [sys.executable, "-m", "ruff", "format", ".", "--check"], True),
        ("Mypy Type Check", [sys.executable, "-m", "mypy", ".", "--ignore-missing-imports"], False),
        (
            "Unit Tests with Coverage",
            [sys.executable, "-m", "pytest", "tests/", "-v", "--cov=."],
            True,
        ),
        ("Smoke Suite", [sys.executable, "main.py", "--suite", "smoke", "--workers", "4"], True),
        (
            "Property Tests",
            [sys.executable, "-m", "pytest", "tests/test_properties.py", "-v"],
            True,
        ),
    ]

    all_passed = True
    failed_steps = []

    for name, cmd, critical in steps:
        if not run_step(name, cmd):
            if critical:
                all_passed = False
                failed_steps.append(name)
            else:
                print(f"--- (Warning: {name} failed but is not critical for CI gating) ---\n")

    if all_passed:
        print("========================================")
        print("ALL CI STEPS PASSED LOCALLY!")
        print("Safe to commit and push.")
        print("========================================")
        sys.exit(0)
    else:
        print("========================================")
        print("CI STEPS FAILED!")
        print(f"Failed steps: {', '.join(failed_steps)}")
        print("Please fix the issues before committing.")
        print("========================================")
        sys.exit(1)


if __name__ == "__main__":
    main()
