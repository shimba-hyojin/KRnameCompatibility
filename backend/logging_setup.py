"""
구조화(JSON) 로깅 설정.

stdout으로 JSON 한 줄씩 출력한다. Docker -> Datadog Agent 가 그대로 수집하며
Datadog Log Explorer에서 필드별 검색/그래프가 가능해진다.
ddtrace가 주입한 trace_id/span_id가 있으면 함께 넣어 Log-Trace 상관관계를 만든다.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone

SERVICE = os.getenv("DD_SERVICE", "name-compat-api")
DD_ENV = os.getenv("DD_ENV", os.getenv("APP_ENV", "local"))
VERSION = os.getenv("DD_VERSION", "1.0.0")

_RESERVED = set(
    """args asctime created exc_info exc_text filename funcName levelname levelno
    lineno module msecs message msg name pathname process processName relativeCreated
    stack_info thread threadName taskName""".split()
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "status": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
            "service": SERVICE,
            "env": DD_ENV,
            "version": VERSION,
        }

        if record.exc_info:
            payload["error"] = {
                "kind": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]),
                "stack": self.formatException(record.exc_info),
            }

        # extra=... 로 넘긴 커스텀 필드 병합
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value

        # ddtrace 연동 (설치되어 있을 때만)
        try:
            from ddtrace import tracer  # type: ignore

            span = tracer.current_span()
            if span:
                payload["dd.trace_id"] = str(span.trace_id)
                payload["dd.span_id"] = str(span.span_id)
        except Exception:  # noqa: BLE001
            pass

        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # werkzeug 기본 액세스 로그는 Nginx access log와 중복되므로 낮춘다
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
