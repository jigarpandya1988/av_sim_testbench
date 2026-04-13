"""
Simple utility to verify connection to a CARLA server.
Usage: python scripts/verify_carla.py --host localhost --port 2000
"""

import argparse
import sys

try:
    import carla

    print("SUCCESS: carla Python library is installed.")
except ImportError:
    print("ERROR: carla Python library NOT found. Please install it.")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()

    print(f"Connecting to CARLA server at {args.host}:{args.port}...")
    try:
        client = carla.Client(args.host, args.port)
        client.set_timeout(args.timeout)
        world = client.get_world()
        map_name = world.get_map().name
        print("SUCCESS: Connected to CARLA!")
        print(f"Current Map: {map_name}")
        print(f"Simulator Version: {client.get_server_version()}")

        # Test blueprint library access
        bp_lib = world.get_blueprint_library()
        vehicles = bp_lib.filter("vehicle.*")
        print(f"Found {len(vehicles)} vehicle blueprints.")

    except Exception as e:
        print(f"ERROR: Could not connect to CARLA server: {e}")
        print("\nPossible fixes:")
        print("1. Ensure CARLA Simulator is running (CarlaUE4.exe).")
        print(f"2. Check if the port {args.port} is open and correct.")
        print("3. Verify your firewall isn't blocking the connection.")
        sys.exit(1)


if __name__ == "__main__":
    main()
