# ==============================================================================
# Production Dockerfile for Campus Complaint & Resolution System
# Optimized for Render Free Cloud Deployment & Local Development
# ==============================================================================

# Base image: Official lightweight Python runtime
FROM python:3.11-slim

# Set environment flags
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Set container working directory
WORKDIR /app

# Install system dependencies for Pillow (imaging) and PostgreSQL client libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies file first for Docker layer caching
COPY requirements.txt /app/

# Install python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the entire project codebase into the container
COPY . /app/

# Expose the default port (Render will override via $PORT at runtime)
EXPOSE 8000

# Start command: Apply database migrations, collect static assets, and boot Gunicorn WSGI server
CMD ["sh", "-c", "python manage.py migrate && python manage.py collectstatic --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --threads 4 --timeout 60"]
