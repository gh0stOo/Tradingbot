FROM python:3.12-slim

# Metadata
LABEL maintainer="Trading Bot Team"
LABEL version="2.0.0"
LABEL description="Trading Bot with ML - Refactored Architecture"
LABEL architecture="refactored"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir \
    xgboost>=2.0.0 \
    scikit-learn>=1.3.0 \
    joblib>=1.3.0 \
    jinja2>=3.1.0 \
    markupsafe>=2.0.0

# Copy application code
COPY . .

# Create data directory for database and logs
RUN mkdir -p /app/data /app/logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src
ENV TRADING_MODE=PAPER

# Expose port (will be mapped to 1337)
EXPOSE 8000

# Health check - check both API server and general health
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Default command - run API server
CMD ["python", "-m", "uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

