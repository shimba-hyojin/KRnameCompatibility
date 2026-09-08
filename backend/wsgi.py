"""Gunicorn entrypoint:  gunicorn -c gunicorn.conf.py wsgi:app"""

import logging

import db
from app import app  # noqa: F401  (gunicorn이 참조)
from config import Config

log = logging.getLogger("app.wsgi")

if Config.DB_ENABLED:
    try:
        db.init_schema()
    except Exception as exc:  # noqa: BLE001
        # DB가 아직 안 떠 있어도 앱은 기동시킨다 (헬스체크에서 degraded로 노출)
        log.error("startup.schema_init_failed error=%s", exc)
