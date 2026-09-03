# Stage 1: Build stage
FROM python:3.14.3-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    curl \
    python3-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /build

# Copy and install requirements
COPY requirements-top-level.txt .
RUN pip install --no-cache-dir -r requirements-top-level.txt

# Stage 2: Runtime stage
FROM python:3.14.3-slim

# Create non-root user early
RUN useradd -m appuser

# Set working directory
WORKDIR /app

# Install only runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.14/site-packages/ /usr/local/lib/python3.14/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Create and set ownership of necessary directories
RUN mkdir -p static && chown -R appuser:appuser /app

# Copy application code
COPY SimplyTransport SimplyTransport/
COPY migrations migrations/

# Set ownership of application files
RUN chown -R appuser:appuser /app/SimplyTransport /app/migrations

# Switch to non-root user
USER appuser

# Command to run the application
CMD ["uvicorn", "SimplyTransport.app:create_app", "--host", "0.0.0.0", "--port", "8000"] 