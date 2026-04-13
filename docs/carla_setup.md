# CARLA Simulator Integration Guide

This guide describes how to set up and run the AV Sim Testbench with the **CARLA Simulator** for 3D high-fidelity validation.

---

## 1. Prerequisites

### Hardware
- **GPU:** NVIDIA RTX 3060 or better (8GB+ VRAM recommended).
- **RAM:** 16GB+ RAM.
- **Disk:** 20GB+ for CARLA installation and maps.

### Software
- **CARLA Simulator:** Version 0.9.15 (recommended).
- **Python:** 3.11 or 3.12.
- **NVIDIA Drivers:** Latest stable version.

---

## 2. Installation

### A. Download CARLA
1. Download the release from [CARLA GitHub](https://github.com/carla-simulator/carla/releases).
2. Extract the package to a folder (e.g., `C:\CARLA_0.9.15`).

### B. Install Python Client
If you have a local CARLA installation, use our helper script to install the correct client binary:

```bash
# Provide the path to your CARLA folder (e.g., C:\CARLA_0.9.15)
python scripts/install_carla_client.py --path C:\CARLA_0.9.15
```

Alternatively, manually install the matching `.whl` from your CARLA installation:
```bash
pip install C:\CARLA_0.9.15\PythonAPI\carla\dist\carla-0.9.15-cp312-cp312-win_amd64.whl
```
*Note: Python 3.13 is not yet officially supported by CARLA 0.9.15 binaries. If you are on 3.13, you may need to use a Python 3.12 virtual environment.*

### C. Install Testbench Dependencies
```bash
pip install -r requirements.txt
```

---

## 3. Running Simulation

### Step 1: Start CARLA Server
Open a terminal in your CARLA folder and run:
```powershell
# Windows
.\CarlaUE4.exe
```
Or for lower overhead (no 3D window on server):
```powershell
.\CarlaUE4.exe -RenderOffScreen
```

### Step 2: Verify Connection
Run the testbench utility to ensure the connection is working:
```bash
python scripts/verify_carla.py
```

### Step 3: Execute Scenarios
Use the `--sim carla` flag to switch the backend:

```bash
# Run smoke suite with 1 worker (recommended)
python main.py --suite smoke --sim carla --workers 1
```

---

## 4. Features of the CARLA Adapter

The `CarlaSimAdapter` provides the following production-grade features:

- **Synchronous Mode:** Ensures deterministic results by locking the simulator clock to the testbench.
- **Real-time Metrics:**
    - **Collision Detection:** Uses CARLA's collision sensor to detect impacts with NPCs or static objects.
    - **Lane Invasion:** Detects lane departures and boundary crossings.
    - **Physics-based Jerk:** Calculates comfort scores based on actual vehicle acceleration.
- **Environment Control:** Automatically syncs scenario weather (rain, fog) and time of day (day/night) with CARLA.
- **Map Auto-loading:** Switches CARLA maps automatically based on the scenario's `map_id`.

---

## 5. Troubleshooting

- **Connection Timeout:** Ensure CARLA is fully loaded before running the testbench.
- **Low FPS:** If the simulation is too slow, try running with `-quality-level Low` when starting CARLA.
- **Map Not Found:** Ensure the `map_id` in your scenarios (e.g., `Town01`) matches the maps available in your CARLA installation.
