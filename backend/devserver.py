"""
의존성 없는 개발용 서버 (표준 라이브러리만 사용).

Flask / MySQL / Docker 설치 없이 화면과 알고리즘을 바로 확인하고 싶을 때 쓴다.
랭킹은 메모리에만 저장되므로 재시작하면 사라진다.

    python3 devserver.py          # http://localhost:8080

운영에서는 절대 쓰지 않는다 (app.py + gunicorn 사용).
"""

from __future__ import annotations

import json
import os
import random
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from compatibility import OWNER_NAME, OWNER_NAME_JA, calculate
from hangul import (
    CLUSTER_JONGSUNG_STROKES,
    CONSONANT_STROKES,
    DOUBLE_CONSONANT_STROKES,
    STROKE_TABLE,
    VOWEL_STROKES,
    HangulError,
    validate_name,
)

PORT = int(os.getenv("PORT", "8080"))
FRONTEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

ERROR_MESSAGES_JA = {
    "EMPTY": "お名前を入力してください。",
    "NOT_HANGUL": "ハングル（한글）で入力してください。例: 야마다",
    "LENGTH": "2〜8文字のハングルで入力してください。",
}

FALLBACK_MESSAGES = [
    "今日は「ありがとう」を3回言うと運が回ってきます。",
    "迷ったら、いつもと違う道で帰ってみましょう。",
    "小さな親切が、大きなラッキーを連れてきます。",
    "今日の幸運アイテムは温かい飲み物です。",
]

# {partner_name: {...}}
MEMORY_STORE: dict = {}

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "namecompat-dev/1.0"

    # ------------------------------------------------------------ helpers
    def _json(self, payload, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _static(self, path: str) -> None:
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        full = os.path.normpath(os.path.join(FRONTEND, rel))
        if not full.startswith(FRONTEND) or not os.path.isfile(full):
            self.send_error(404, "Not Found")
            return
        ext = os.path.splitext(full)[1]
        with open(full, "rb") as fp:
            body = fp.read()
        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPES.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _stats(self):
        if not MEMORY_STORE:
            return {"total_people": 0, "total_lookups": 0, "avg_score": 0.0}
        scores = [row["score"] for row in MEMORY_STORE.values()]
        return {
            "total_people": len(MEMORY_STORE),
            "total_lookups": sum(row["lookup_count"] for row in MEMORY_STORE.values()),
            "avg_score": round(sum(scores) / len(scores), 1),
        }

    # ------------------------------------------------------------ routes
    def do_GET(self):  # noqa: N802
        route = urlparse(self.path)

        if route.path == "/api/health":
            return self._json({"status": "ok", "env": "dev", "db": "memory"})

        if route.path == "/api/meta":
            return self._json(
                {
                    "owner_name": OWNER_NAME,
                    "owner_name_ja": OWNER_NAME_JA,
                    "stats": self._stats(),
                }
            )

        if route.path == "/api/ranking":
            limit = int((parse_qs(route.query).get("limit") or ["20"])[0])
            rows = sorted(
                MEMORY_STORE.values(), key=lambda r: (-r["score"], r["partner_name"])
            )[:limit]
            ranking = [
                {
                    "rank": idx,
                    "partner_name": row["partner_name"],
                    "score": row["score"],
                    "grade_label": row["grade_label"],
                    "lookup_count": row["lookup_count"],
                    "created_at": None,
                }
                for idx, row in enumerate(rows, start=1)
            ]
            return self._json(
                {"owner_name": OWNER_NAME, "ranking": ranking, "stats": self._stats()}
            )

        if route.path == "/api/fortune":
            return self._json(
                {
                    "message": random.choice(FALLBACK_MESSAGES),
                    "sign": None,
                    "item": None,
                    "total": None,
                    "source": "fallback",
                }
            )

        if route.path == "/api/stroke-table":
            return self._json(
                {
                    "consonants": CONSONANT_STROKES,
                    "double_consonants": DOUBLE_CONSONANT_STROKES,
                    "cluster_jongsung": CLUSTER_JONGSUNG_STROKES,
                    "vowels": VOWEL_STROKES,
                    "total_entries": len(STROKE_TABLE),
                }
            )

        if route.path.startswith("/api/"):
            return self._json({"error": "NOT_FOUND"}, 404)

        return self._static(route.path)

    def do_POST(self):  # noqa: N802
        route = urlparse(self.path)
        if route.path != "/api/compatibility":
            return self._json({"error": "NOT_FOUND"}, 404)

        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            body = {}

        try:
            result = calculate(body.get("partner_name", ""), owner_name=OWNER_NAME)
        except HangulError as exc:
            code = str(exc)
            return self._json(
                {"error": code, "message": ERROR_MESSAGES_JA.get(code, "入力を確認してください。")},
                400,
            )

        payload = result.to_dict()
        stored = MEMORY_STORE.get(result.partner_name)
        MEMORY_STORE[result.partner_name] = {
            "partner_name": result.partner_name,
            "score": result.score,
            "grade_label": result.grade_label,
            "lookup_count": (stored["lookup_count"] + 1) if stored else 1,
        }
        payload["saved"] = True
        return self._json(payload)

    def do_DELETE(self):  # noqa: N802
        route = urlparse(self.path)

        if route.path == "/api/ranking":
            count = len(MEMORY_STORE)
            MEMORY_STORE.clear()
            return self._json({"deleted": count, "message": f"{count}件を削除しました。"})

        if route.path.startswith("/api/ranking/"):
            target = unquote(route.path[len("/api/ranking/"):])
            try:
                name = validate_name(target)
            except HangulError as exc:
                code = str(exc)
                return self._json(
                    {"error": code, "message": ERROR_MESSAGES_JA.get(code, "入力を確認してください。")},
                    400,
                )
            if name not in MEMORY_STORE:
                return self._json(
                    {"deleted": 0, "message": f"「{name}」の記録は見つかりませんでした。"}, 404
                )
            del MEMORY_STORE[name]
            return self._json({"deleted": 1, "message": f"「{name}」を削除しました。"})

        return self._json({"error": "NOT_FOUND"}, 404)

    def log_message(self, fmt, *args):  # 간단한 액세스 로그
        print("[dev] " + fmt % args)


if __name__ == "__main__":
    print(f"開発サーバー起動: http://localhost:{PORT}  (静的ファイル: {FRONTEND})")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
