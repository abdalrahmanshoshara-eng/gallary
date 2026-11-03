"""Gunicorn config for the `realtime` process: Django ASGI + Channels on Uvicorn workers (ADR-08)."""

import os

bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:8001")
worker_class = "uvicorn_worker.UvicornWorker"
workers = int(os.environ.get("GUNICORN_WORKERS", 2))
# Long-lived WebSockets: the worker timeout only applies to the heartbeat with the arbiter.
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 60))
# On redeploy, connections are closed with 1012 and clients reconnect with jittered backoff.
graceful_timeout = int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", 20))
keepalive = 5
forwarded_allow_ips = os.environ.get("GUNICORN_FORWARDED_ALLOW_IPS", "*")
accesslog = "-"
errorlog = "-"
control_socket_disable = True
