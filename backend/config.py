"""환경변수 기반 설정. 12-factor 스타일로 코드에 비밀값을 넣지 않는다."""

import os


def _bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).strip().lower() in ("1", "true", "yes", "on")


class Config:
    # --- App ---
    ENV = os.getenv("APP_ENV", "local")            # local | prod
    PORT = int(os.getenv("PORT", "8000"))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    SERVE_STATIC = _bool("SERVE_STATIC", True)     # prod에서는 Nginx가 담당 -> false 권장
    OWNER_NAME = os.getenv("OWNER_NAME", "심효진")
    OWNER_NAME_JA = os.getenv("OWNER_NAME_JA", "シム・ヒョジン")

    # --- Database (MySQL / Amazon RDS for MySQL) ---
    DB_ENABLED = _bool("DB_ENABLED", True)
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER", "appuser")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "apppassword")
    DB_NAME = os.getenv("DB_NAME", "namecompat")
    DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "5"))

    # --- External Fortune API ---
    FORTUNE_API_URL = os.getenv("FORTUNE_API_URL", "https://jugemkey.jp/api/waf/api.php")
    FORTUNE_API_KEY = os.getenv("FORTUNE_API_KEY", "Fortune")
    FORTUNE_TIMEOUT = float(os.getenv("FORTUNE_TIMEOUT", "3.0"))
    FORTUNE_CACHE_TTL = int(os.getenv("FORTUNE_CACHE_TTL", "600"))  # 초

    # --- Ranking ---
    RANKING_LIMIT_DEFAULT = int(os.getenv("RANKING_LIMIT_DEFAULT", "20"))
    RANKING_LIMIT_MAX = int(os.getenv("RANKING_LIMIT_MAX", "100"))

    # --- Admin (삭제 API 보호) ---
    # 비어 있으면 삭제 API가 무인증으로 열린다. SSH 터널 전용 개인 환경에서는 그대로 두고,
    # 외부에 공개할 때는 반드시 값을 채운다 (프론트엔드는 X-Admin-Token 헤더로 전송).
    ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "").strip()
