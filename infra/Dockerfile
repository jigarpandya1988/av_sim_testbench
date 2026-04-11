FROM python:3.11-slim AS base

LABEL maintainer="av-sim-testbench"
LABEL description="AV Simulation Testbench worker image"

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Default: run full suite
ENTRYPOINT ["python", "main.py"]
CMD ["--suite", "full", "--workers", "8"]

# ---- CI/test stage ----
FROM base AS test
RUN pip install --no-cache-dir pytest pytest-asyncio pytest-cov hypothesis
CMD ["pytest", "tests/", "-v", "--tb=short", "--cov=.", "--cov-report=xml"]
