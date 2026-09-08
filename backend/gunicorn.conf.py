"""Gunicorn 설정. EC2 t3.micro(2 vCPU) 기준."""

import multiprocessing
import os

bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
workers = int(os.getenv("GUNICORN_WORKERS", str(min(4, multiprocessing.cpu_count() * 2 + 1))))
threads = int(os.getenv("GUNICORN_THREADS", "2"))
worker_class = "gthread"
timeout = 30
graceful_timeout = 20
keepalive = 5

# 액세스 로그는 Nginx에서 남기므로 여기서는 에러만 stdout으로
accesslog = None
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()
