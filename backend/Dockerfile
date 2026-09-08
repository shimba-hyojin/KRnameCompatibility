# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 의존성 먼저 복사 -> 레이어 캐시 활용
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 비root 유저로 실행 (보안)
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2).status==200 else 1)"

# ddtrace-run 으로 감싸면 Datadog APM 트레이싱이 자동 계측된다.
# DD_TRACE_ENABLED=false 이면 ddtrace-run은 아무 일도 하지 않으므로 그대로 두면 된다.
CMD ["ddtrace-run", "gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]
