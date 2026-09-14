"""
Gunicorn Production Server Configuration.
Optimized for lightweight container deployment on Render Free Plan.
"""

import os
import multiprocessing

# Network socket binding
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

# Concurrency & worker configuration
# 2 workers with 4 threads per worker allows handling concurrent requests within free tier memory limits (~512MB)
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "4"))
worker_class = "gthread"

# Request timeouts
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))
keepalive = 5

# Logging to standard output for Docker / Render log stream aggregation
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")

# Graceful worker restart
max_requests = 1000
max_requests_jitter = 50
