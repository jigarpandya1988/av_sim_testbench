r"""
Helper script to install the CARLA Python client from a local CARLA installation.
Usage: python scripts/install_carla_client.py --path C:\CARLA_0.9.15
"""

import argparse
import os
import subprocess
import sys


def find_whl_file(carla_path: str, python_version: str) -> str | None:
    """Look for the .whl or .egg file in the CARLA distribution."""
    # Common path for CARLA releases: PythonAPI/carla/dist/
    dist_path = os.path.join(carla_path, "PythonAPI", "carla", "dist")
    if not os.path.exists(dist_path):
        print(f"Error: Distribution folder not found: {dist_path}")
        return None

    # Try to find a .whl file matching the current Python version
    files = os.listdir(dist_path)
    target_pattern = f"cp{python_version.replace('.', '')}"

    # Try .whl files first (best practice)
    whl_files = [f for f in files if f.endswith(".whl") and target_pattern in f]
    if whl_files:
        return os.path.join(dist_path, whl_files[0])

    # Fallback to .egg if no .whl matches
    egg_files = [f for f in files if f.endswith(".egg") and target_pattern in f]
    if egg_files:
        return os.path.join(dist_path, egg_files[0])

    print(f"Warning: No matching client binary found for Python {python_version} in {dist_path}")
    print("Available files:")
    for f in files:
        if f.endswith((".whl", ".egg")):
            print(f" - {f}")
    return None


def main():
    parser = argparse.ArgumentParser(description="Install CARLA Python Client.")
    parser.add_argument("--path", required=True, help="Path to your CARLA installation folder.")
    args = parser.parse_args()

    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    print(f"Current Python version: {python_version}")

    whl_path = find_whl_file(args.path, python_version)
    if not whl_path:
        print("\nTIP: CARLA 0.9.15 officially supports Python 3.7 up to 3.12.")
        print(
            f"You are running {python_version}. Consider using a Python 3.12 environment if possible."
        )
        sys.exit(1)

    print(f"Found client binary: {whl_path}")
    print("Installing...")

    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", whl_path])
        print("\nSUCCESS: CARLA Python client installed!")
        print("You can now run: python scripts/verify_carla.py")
    except subprocess.CalledProcessError as e:
        print(f"\nERROR: Installation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
