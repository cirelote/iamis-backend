bind = "0.0.0.0:8000"  # Bind to all IPs on port 8000
workers = 2  # Adjust based on your server's CPU cores
worker_class = "uvicorn.workers.UvicornWorker"  # Use uvicorn worker for async support
accesslog = "-"  # Log access to stdout
errorlog = "-"  # Log errors to stdout
