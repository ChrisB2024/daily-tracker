FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy all files first
COPY . .

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e .

# Expose port
EXPOSE 8000

# Run the app
# `|| true` was removed 2026-09-07. A failed migration now stops the container,
# so Railway keeps serving the previous one and the deploy shows as failed —
# rather than booting green against the old schema and 500ing at runtime.
CMD sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"
