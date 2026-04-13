FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies (for aiosqlite / native packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY . .

# Ensure the data directory exists (SQLite DB will live here when mounted)
RUN mkdir -p /app/data

# Expose the FastAPI port
EXPOSE 8000

# Run uvicorn — data dir is mounted at /app/data via docker-compose volume
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
