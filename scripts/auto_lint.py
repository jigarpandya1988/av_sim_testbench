import subprocess
import sys


def run_command(name, command):
    print(f"--- Running {name} ---")
    print(f"Command: {' '.join(command)}")
    try:
        subprocess.run(command, check=True, capture_output=False)
        print(f"--- {name} COMPLETED SUCCESSFULLY ---\n")
        return True
    except subprocess.CalledProcessError as e:
        print(f"!!! {name} FAILED !!! (Exit code: {e.returncode})\n")
        return False


def main():
    # ruff check with --fix and ruff format are the two key components of auto linting
    # We include I (isort) in the select list for better organization, as configured in pyproject.toml

    commands = [
        ("Ruff Fix", [sys.executable, "-m", "ruff", "check", ".", "--fix"]),
        ("Ruff Format", [sys.executable, "-m", "ruff", "format", "."]),
    ]

    success = True
    for name, cmd in commands:
        if not run_command(name, cmd):
            success = False
            # Don't stop on first failure as multiple tools might fix different things

    if success:
        print("Auto-linting completed successfully. Your code should be clean and formatted.")
        sys.exit(0)
    else:
        print("Auto-linting encountered some issues that could not be automatically fixed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
