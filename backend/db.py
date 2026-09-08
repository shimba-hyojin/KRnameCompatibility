"""
MySQL(Amazon RDS for MySQL) 접근 계층.

- SQL은 전부 파라미터 바인딩 (SQL Injection 방어)
- DB 장애가 서비스 전체 장애로 번지지 않도록, 저장 실패는 로깅 후 무시하고
  진단 결과 자체는 사용자에게 반환한다 (graceful degradation)
"""

from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

import pymysql
from pymysql.cursors import DictCursor

from config import Config

log = logging.getLogger("app.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS compatibility_results (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    owner_name      VARCHAR(20)     NOT NULL,
    partner_name    VARCHAR(20)     NOT NULL,
    score           TINYINT UNSIGNED NOT NULL,
    grade_label     VARCHAR(32)     NOT NULL,
    detail          JSON            NULL,
    lookup_count    INT UNSIGNED    NOT NULL DEFAULT 1,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP
                                    ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_owner_partner (owner_name, partner_name),
    KEY idx_score (score DESC, created_at ASC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""


def _connect() -> pymysql.connections.Connection:
    return pymysql.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=True,
        connect_timeout=Config.DB_CONNECT_TIMEOUT,
    )


@contextmanager
def cursor():
    """요청 단위 커넥션. 규모가 커지면 SQLAlchemy 커넥션 풀로 교체."""
    conn = _connect()
    try:
        with conn.cursor() as cur:
            yield cur
    finally:
        conn.close()


def init_schema() -> None:
    """앱 시작 시 테이블을 보장한다 (idempotent)."""
    if not Config.DB_ENABLED:
        log.warning("db.disabled - schema init skipped")
        return
    with cursor() as cur:
        cur.execute(SCHEMA_SQL)
    log.info("db.schema_ready")


def ping() -> bool:
    """헬스체크용."""
    if not Config.DB_ENABLED:
        return False
    try:
        with cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("db.ping_failed error=%s", exc)
        return False


def save_result(result: Dict[str, Any]) -> bool:
    """
    진단 결과를 저장(UPSERT)한다.
    같은 (owner, partner) 조합은 점수가 항상 같으므로 행을 늘리지 않고
    lookup_count 만 증가시킨다. -> 랭킹에 같은 사람이 중복 표시되지 않는다.
    """
    if not Config.DB_ENABLED:
        return False

    sql = """
        INSERT INTO compatibility_results
            (owner_name, partner_name, score, grade_label, detail)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            score        = VALUES(score),
            grade_label  = VALUES(grade_label),
            detail       = VALUES(detail),
            lookup_count = lookup_count + 1
    """
    started = time.perf_counter()
    try:
        with cursor() as cur:
            cur.execute(
                sql,
                (
                    result["owner_name"],
                    result["partner_name"],
                    result["score"],
                    result["grade"]["label"],
                    json.dumps(result["steps"], ensure_ascii=False),
                ),
            )
        log.info(
            "db.save_result ok partner=%s score=%s duration_ms=%.1f",
            result["partner_name"],
            result["score"],
            (time.perf_counter() - started) * 1000,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("db.save_result_failed partner=%s error=%s", result.get("partner_name"), exc)
        return False


def fetch_ranking(limit: int) -> List[Dict[str, Any]]:
    """궁합 점수 내림차순 랭킹."""
    if not Config.DB_ENABLED:
        return []

    sql = """
        SELECT partner_name, score, grade_label, lookup_count, created_at
        FROM compatibility_results
        WHERE owner_name = %s
        ORDER BY score DESC, created_at ASC
        LIMIT %s
    """
    with cursor() as cur:
        cur.execute(sql, (Config.OWNER_NAME, int(limit)))
        rows = cur.fetchall()

    ranking: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        ranking.append(
            {
                "rank": idx,
                "partner_name": row["partner_name"],
                "score": int(row["score"]),
                "grade_label": row["grade_label"],
                "lookup_count": int(row["lookup_count"]),
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
        )
    return ranking


def delete_result(partner_name: str) -> int:
    """
    특정 상대 이름의 진단 기록을 삭제한다. 삭제된 행 수를 반환.
    """
    if not Config.DB_ENABLED:
        return 0

    sql = """
        DELETE FROM compatibility_results
        WHERE owner_name = %s AND partner_name = %s
    """
    with cursor() as cur:
        deleted = cur.execute(sql, (Config.OWNER_NAME, partner_name))
    log.info("db.delete_result partner=%s deleted=%s", partner_name, deleted)
    return int(deleted)


def delete_all() -> int:
    """
    본인(owner_name) 기준 전체 진단 기록을 삭제한다. 삭제된 행 수를 반환.
    """
    if not Config.DB_ENABLED:
        return 0

    sql = "DELETE FROM compatibility_results WHERE owner_name = %s"
    with cursor() as cur:
        deleted = cur.execute(sql, (Config.OWNER_NAME,))
    log.warning("db.delete_all deleted=%s", deleted)
    return int(deleted)


def fetch_stats() -> Optional[Dict[str, Any]]:
    """총 진단 수 / 평균 점수 (관찰용 지표)."""
    if not Config.DB_ENABLED:
        return None
    with cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS total_people,
                   COALESCE(SUM(lookup_count), 0) AS total_lookups,
                   COALESCE(ROUND(AVG(score), 1), 0) AS avg_score
            FROM compatibility_results
            WHERE owner_name = %s
            """,
            (Config.OWNER_NAME,),
        )
        row = cur.fetchone()
    if not row:
        return None
    return {
        "total_people": int(row["total_people"]),
        "total_lookups": int(row["total_lookups"]),
        "avg_score": float(row["avg_score"]),
    }
