-- =====================================================================
--  name-compat  스키마
--  로컬: docker-entrypoint-initdb.d 로 자동 실행
--  RDS : mysql -h <endpoint> -u admin -p < db/init.sql
-- =====================================================================

CREATE DATABASE IF NOT EXISTS namecompat
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE namecompat;

-- ---------------------------------------------------------------------
-- 궁합 진단 결과
--  * (owner_name, partner_name) 은 UNIQUE.
--    동일 입력은 항상 동일 점수이므로 행을 늘리지 않고 lookup_count만 올린다.
--  * detail 에는 계산 과정(JSON)을 그대로 보관해 나중에 분석/재현이 가능하다.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS compatibility_results (
    id              BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
    owner_name      VARCHAR(20)      NOT NULL COMMENT '본인 이름 (고정: 심효진)',
    partner_name    VARCHAR(20)      NOT NULL COMMENT '상대 이름 (한글)',
    score           TINYINT UNSIGNED NOT NULL COMMENT '궁합 점수 0-99',
    grade_label     VARCHAR(32)      NOT NULL COMMENT '등급 라벨(일본어)',
    detail          JSON             NULL     COMMENT '계산 과정 전체',
    lookup_count    INT UNSIGNED     NOT NULL DEFAULT 1 COMMENT '조회 횟수',
    created_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP
                                     ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_owner_partner (owner_name, partner_name),
    KEY idx_score (score DESC, created_at ASC)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='이름 궁합 진단 결과';

-- ---------------------------------------------------------------------
-- 애플리케이션 전용 계정 (RDS에서 실행할 때만 사용)
-- 비밀번호는 실제 값으로 바꾼 뒤 실행하고, 히스토리에 남지 않게 주의한다.
-- 삭제 기능을 쓰려면 DELETE 권한이 필요하다.
-- ---------------------------------------------------------------------
-- CREATE USER IF NOT EXISTS 'appuser'@'%' IDENTIFIED BY 'CHANGE_ME';
-- GRANT SELECT, INSERT, UPDATE, DELETE ON namecompat.* TO 'appuser'@'%';
-- FLUSH PRIVILEGES;

-- ---------------------------------------------------------------------
-- Datadog Database Monitoring 용 계정 (선택)
-- ---------------------------------------------------------------------
-- CREATE USER IF NOT EXISTS 'datadog'@'%' IDENTIFIED BY 'CHANGE_ME';
-- GRANT REPLICATION CLIENT ON *.* TO 'datadog'@'%' WITH MAX_USER_CONNECTIONS 5;
-- GRANT PROCESS ON *.* TO 'datadog'@'%';
-- GRANT SELECT ON performance_schema.* TO 'datadog'@'%';
