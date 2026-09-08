"""
韓国式 名前相性診断 — Backend API (Flask)

Endpoints
---------
GET    /api/health              헬스체크 (DB 연결 상태 포함)
GET    /api/meta                본인 이름 등 화면 초기화용 메타 정보
POST   /api/compatibility       궁합 진단 (계산 과정 포함)
GET    /api/ranking             궁합 랭킹 (score DESC)
DELETE /api/ranking             랭킹 전체 삭제
DELETE /api/ranking/<이름>      특정 이름의 기록 삭제
GET    /api/fortune             포춘쿠키 (외부 API)
GET    /api/stroke-table        획수표 (仕組みページ 표시용)
"""

from __future__ import annotations

import logging
import os
import time
import uuid

from flask import Flask, g, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

import db
from compatibility import calculate
from config import Config
from fortune import open_cookie
from hangul import (
    CLUSTER_JONGSUNG_STROKES,
    CONSONANT_STROKES,
    DOUBLE_CONSONANT_STROKES,
    STROKE_TABLE,
    VOWEL_STROKES,
    HangulError,
    validate_name,
)
from logging_setup import setup_logging

setup_logging(Config.LOG_LEVEL)
log = logging.getLogger("app")

FRONTEND_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "frontend")
)

# 검증 에러 -> 일본어 메시지
ERROR_MESSAGES_JA = {
    "EMPTY": "お名前を入力してください。",
    "NOT_HANGUL": "ハングル（한글）で入力してください。例: 야마다",
    "LENGTH": "2〜8文字のハングルで入力してください。",
}


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder=FRONTEND_DIR if Config.SERVE_STATIC else None,
        static_url_path="",
    )

    # ---------------------------------------------------------------- 미들웨어
    @app.before_request
    def _start_timer():
        g.started_at = time.perf_counter()
        g.request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:16]

    @app.after_request
    def _log_request(response):
        duration_ms = (time.perf_counter() - getattr(g, "started_at", time.perf_counter())) * 1000
        if request.path.startswith("/api/"):
            log.info(
                "http.request",
                extra={
                    "http": {
                        "method": request.method,
                        "url": request.path,
                        "status_code": response.status_code,
                    },
                    "duration_ms": round(duration_ms, 2),
                    "request_id": getattr(g, "request_id", None),
                },
            )
        response.headers["X-Request-Id"] = getattr(g, "request_id", "")
        return response

    @app.errorhandler(404)
    def _not_found(_e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "NOT_FOUND"}), 404
        # SPA는 아니지만, 오타 URL은 첫 화면으로 돌려보낸다
        if Config.SERVE_STATIC:
            return send_from_directory(FRONTEND_DIR, "index.html")
        return jsonify({"error": "NOT_FOUND"}), 404

    @app.errorhandler(Exception)
    def _internal_error(exc):
        # 405/413 등 정상적인 HTTP 예외는 그대로 통과시킨다
        if isinstance(exc, HTTPException):
            if request.path.startswith("/api/"):
                return jsonify({"error": exc.name.upper().replace(" ", "_")}), exc.code
            return exc
        log.exception("http.unhandled_error path=%s", request.path)
        return jsonify({"error": "INTERNAL_ERROR", "message": "サーバーエラーが発生しました。"}), 500

    # ---------------------------------------------------------------- API
    @app.get("/api/health")
    def health():
        db_ok = db.ping()
        return jsonify(
            {
                "status": "ok" if (db_ok or not Config.DB_ENABLED) else "degraded",
                "env": Config.ENV,
                "db": "ok" if db_ok else ("disabled" if not Config.DB_ENABLED else "down"),
            }
        ), 200

    @app.get("/api/meta")
    def meta():
        return jsonify(
            {
                "owner_name": Config.OWNER_NAME,
                "owner_name_ja": Config.OWNER_NAME_JA,
                "stats": _safe_stats(),
            }
        )

    @app.post("/api/compatibility")
    def compatibility():
        body = request.get_json(silent=True) or {}
        partner_name = body.get("partner_name", "")

        try:
            result = calculate(partner_name, owner_name=Config.OWNER_NAME)
        except HangulError as exc:
            code = str(exc)
            log.warning(
                "compatibility.validation_failed",
                extra={"code": code, "input_length": len(str(partner_name))},
            )
            return jsonify(
                {"error": code, "message": ERROR_MESSAGES_JA.get(code, "入力を確認してください。")}
            ), 400

        payload = result.to_dict()
        payload["saved"] = db.save_result(payload)

        log.info(
            "compatibility.calculated",
            extra={
                "partner_name": result.partner_name,
                "score": result.score,
                "grade": result.grade_label,
                "saved": payload["saved"],
            },
        )
        return jsonify(payload), 200

    @app.get("/api/ranking")
    def ranking():
        try:
            limit = int(request.args.get("limit", Config.RANKING_LIMIT_DEFAULT))
        except ValueError:
            limit = Config.RANKING_LIMIT_DEFAULT
        limit = max(1, min(limit, Config.RANKING_LIMIT_MAX))

        try:
            rows = db.fetch_ranking(limit)
        except Exception as exc:  # noqa: BLE001
            log.error("ranking.query_failed error=%s", exc)
            return jsonify({"error": "DB_UNAVAILABLE", "message": "ランキングを取得できませんでした。"}), 503

        return jsonify({"owner_name": Config.OWNER_NAME, "ranking": rows, "stats": _safe_stats()})

    @app.delete("/api/ranking")
    def delete_ranking_all():
        """랭킹 전체 삭제. ADMIN_TOKEN이 설정되어 있으면 헤더 검증."""
        if not _admin_ok():
            return jsonify({"error": "FORBIDDEN", "message": "権限がありません。"}), 403

        try:
            deleted = db.delete_all()
        except Exception as exc:  # noqa: BLE001
            log.error("ranking.delete_all_failed error=%s", exc)
            return jsonify({"error": "DB_UNAVAILABLE", "message": "削除できませんでした。"}), 503

        log.warning("ranking.deleted_all", extra={"deleted": deleted})
        return jsonify({"deleted": deleted, "message": f"{deleted}件を削除しました。"})

    @app.delete("/api/ranking/<partner_name>")
    def delete_ranking_one(partner_name: str):
        """특정 이름의 진단 기록 삭제."""
        if not _admin_ok():
            return jsonify({"error": "FORBIDDEN", "message": "権限がありません。"}), 403

        try:
            name = validate_name(partner_name)
        except HangulError as exc:
            code = str(exc)
            return jsonify(
                {"error": code, "message": ERROR_MESSAGES_JA.get(code, "入力を確認してください。")}
            ), 400

        try:
            deleted = db.delete_result(name)
        except Exception as exc:  # noqa: BLE001
            log.error("ranking.delete_failed partner=%s error=%s", name, exc)
            return jsonify({"error": "DB_UNAVAILABLE", "message": "削除できませんでした。"}), 503

        if deleted == 0:
            return jsonify(
                {"deleted": 0, "message": f"「{name}」の記録は見つかりませんでした。"}
            ), 404

        log.info("ranking.deleted_one", extra={"partner_name": name, "deleted": deleted})
        return jsonify({"deleted": deleted, "message": f"「{name}」を削除しました。"})

    @app.get("/api/fortune")
    def fortune():
        cookie = open_cookie()
        log.info("fortune.opened", extra={"source": cookie["source"]})
        return jsonify(cookie)

    @app.get("/api/stroke-table")
    def stroke_table():
        return jsonify(
            {
                "consonants": CONSONANT_STROKES,
                "double_consonants": DOUBLE_CONSONANT_STROKES,
                "cluster_jongsung": CLUSTER_JONGSUNG_STROKES,
                "vowels": VOWEL_STROKES,
                "total_entries": len(STROKE_TABLE),
            }
        )

    # ---------------------------------------------------------------- static
    if Config.SERVE_STATIC:
        @app.get("/")
        def index():
            return send_from_directory(FRONTEND_DIR, "index.html")

    return app


def _admin_ok() -> bool:
    """
    ADMIN_TOKEN 이 설정되어 있으면 X-Admin-Token 헤더가 일치해야 한다.
    비어 있으면(기본) 누구나 삭제 가능 — SSH 터널로만 접근하는 개인 환경 전제.
    외부에 공개할 때는 반드시 ADMIN_TOKEN 을 설정한다.
    """
    if not Config.ADMIN_TOKEN:
        return True
    return request.headers.get("X-Admin-Token") == Config.ADMIN_TOKEN


def _safe_stats():
    try:
        return db.fetch_stats()
    except Exception as exc:  # noqa: BLE001
        log.error("stats.query_failed error=%s", exc)
        return None


app = create_app()

if __name__ == "__main__":
    if Config.DB_ENABLED:
        try:
            db.init_schema()
        except Exception as exc:  # noqa: BLE001
            log.error("startup.schema_init_failed error=%s", exc)
    app.run(host="0.0.0.0", port=Config.PORT, debug=(Config.ENV == "local"))
