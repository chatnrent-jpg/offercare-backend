# --- Stage 1: Build & Dependency Isolation ---
FROM python:3.11-slim AS builder

WORKDIR /build

# Install system compilation packages needed for database drivers
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements to leverage Docker caching layers
COPY requirements.txt .

# Install dependencies into a localized wheelhouse directory
RUN pip install --no-cache-dir --user -r requirements.txt

# --- Stage 2: Final Secure Production Runtime ---
FROM python:3.11-slim AS runner

WORKDIR /app

# Install minimal runtime library dependencies for PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed libraries from the builder stage
COPY --from=builder /root/.local /root/.local
COPY . /app

# Ensure Python can find the user-installed modules
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/app

# Expose production ASGI server port
EXPOSE 8000

# Enforce non-root execution rules for secure cloud infrastructure
USER 10001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
