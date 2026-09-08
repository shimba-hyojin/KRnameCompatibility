"""
포춘쿠키 기능 — 외부 Fortune API 연동.

API: https://jugemkey.jp/api/waf/api.php  (JugemKey 「WebAPI 占い」)
  파라미터 예: ?api_key=<KEY>&api_mode=fortune&api_year=1995&api_month=5&api_day=20

설계 포인트
-----------
* 외부 API는 언제든 느려지거나 죽는다 -> timeout + fallback 필수.
  (이 fallback 경로가 Datadog에서 external API 에러율을 관찰하는 좋은 실습 소재가 된다)
* 응답 스키마 변화에 강하도록, 재귀 탐색으로 "content" 를 가진 객체를 수집한다.
* 짧은 TTL 캐시로 외부 API 호출량을 줄인다.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any, Dict, List, Optional

import requests

from config import Config

log = logging.getLogger("app.fortune")

# API 장애 시 사용할 로컬 메시지 (일본어)
FALLBACK_MESSAGES: List[str] = [
    "今日は「ありがとう」を3回言うと運が回ってきます。",
    "迷ったら、いつもと違う道で帰ってみましょう。",
    "小さな親切が、大きなラッキーを連れてきます。",
    "今日の幸運アイテムは温かい飲み物です。",
    "返事を後回しにしているメッセージ、今送ると吉。",
    "笑顔は最強のラッキーチャームです。",
    "昼休みに5分だけ空を見上げてみてください。",
    "今日は聞き役に回ると、いい情報が入ってきます。",
]

_cache: Dict[str, Any] = {"data": None, "expires_at": 0.0}


def _collect_fortunes(node: Any, acc: List[Dict[str, Any]]) -> None:
    """응답 JSON을 재귀 탐색하여 'content' 키를 가진 객체를 모은다."""
    if isinstance(node, dict):
        if isinstance(node.get("content"), str) and node["content"].strip():
            acc.append(node)
        for value in node.values():
            _collect_fortunes(value, acc)
    elif isinstance(node, list):
        for item in node:
            _collect_fortunes(item, acc)


def _fetch_from_api() -> Optional[Dict[str, Any]]:
    """외부 API 호출. 실패 시 None."""
    # 날짜 파라미터는 필수이므로 오늘 날짜를 사용한다.
    today = time.localtime()
    params = {
        "api_key": Config.FORTUNE_API_KEY,
        "api_mode": "fortune",
        "api_year": today.tm_year,
        "api_month": today.tm_mon,
        "api_day": today.tm_mday,
    }

    started = time.perf_counter()
    try:
        resp = requests.get(
            Config.FORTUNE_API_URL,
            params=params,
            timeout=Config.FORTUNE_TIMEOUT,
            headers={"User-Agent": "name-compat/1.0"},
        )
        duration_ms = (time.perf_counter() - started) * 1000
        log.info(
            "fortune.api_call status=%s duration_ms=%.1f",
            resp.status_code,
            duration_ms,
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        log.error(
            "fortune.api_failed error=%s duration_ms=%.1f",
            exc,
            (time.perf_counter() - started) * 1000,
        )
        return None

    found: List[Dict[str, Any]] = []
    _collect_fortunes(payload, found)
    if not found:
        log.error(
            "fortune.api_unexpected_schema keys=%s",
            list(payload)[:5] if isinstance(payload, dict) else type(payload),
        )
        return None

    return {"items": found}


def _get_items() -> Optional[List[Dict[str, Any]]]:
    """TTL 캐시를 통해 API 결과를 얻는다."""
    now = time.time()
    if _cache["data"] and now < _cache["expires_at"]:
        return _cache["data"]["items"]

    fetched = _fetch_from_api()
    if fetched:
        _cache["data"] = fetched
        _cache["expires_at"] = now + Config.FORTUNE_CACHE_TTL
        return fetched["items"]
    return None


def open_cookie() -> Dict[str, Any]:
    """
    포춘쿠키를 하나 뽑는다.
    반환: {message, sign, item, source}
      source = "api"      -> 외부 API 응답
      source = "fallback" -> 외부 API 실패 시 로컬 메시지
    """
    items = _get_items()
    if items:
        picked = random.choice(items)
        return {
            "message": str(picked.get("content", "")).strip(),
            "sign": picked.get("sign") or None,
            "item": picked.get("item") or None,
            "total": picked.get("total"),
            "source": "api",
        }

    return {
        "message": random.choice(FALLBACK_MESSAGES),
        "sign": None,
        "item": None,
        "total": None,
        "source": "fallback",
    }
