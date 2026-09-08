**한국어** | [日本語](monitors.md)

# Datadog 모니터 / 대시보드 / 트레이스 설계

설계서 8장의 관찰 대상을 실제 설정으로 옮긴 것. Datadog UI에서 그대로 만들 수 있다.

## 1. 수집 경로 정리

| 관찰 대상 | 수집 방법 | 주요 메트릭 |
|---|---|---|
| EC2 (CPU/Mem/Disk/Net) | Datadog Agent (기본 system check) | `system.cpu.user`, `system.mem.pct_usable`, `system.disk.in_use`, `system.net.bytes_rcvd` |
| Nginx 요청/응답 | nginx integration (`stub_status`) + JSON access log | `nginx.net.request_per_s`, `nginx.net.connections`, 로그의 `request_time` |
| Application | ddtrace(APM) + 구조화 로그 | `trace.flask.request.hits/errors/duration` |
| **DB 쿼리** | ddtrace pymysql 자동 계측 | `trace.pymysql.query.duration` |
| 외부 Fortune API | 앱 로그 (`fortune.api_call` / `fortune.api_failed`) + http_check | 로그 기반 메트릭 |
| RDS | mysql integration + CloudWatch(AWS integration) | `mysql.performance.queries`, `mysql.net.connections`, `aws.rds.cpuutilization`, `aws.rds.free_storage_space` |

## 1-2. APM 트레이스와 DB 스팬 (트레이스 ↔ 로그 ↔ 쿼리)

`ddtrace-run` 이 Flask와 **pymysql을 자동 계측**하므로, 별도 코드 없이 요청 하나가
아래 형태의 트레이스로 잡힌다.

```
flask.request  POST /api/compatibility          12.4ms
├─ flask.dispatch                                11.8ms
│  └─ pymysql.query  INSERT INTO compatibility…   8.2ms   ← DB 스팬
└─ (fortune 호출 시) requests.request             3.1ms   ← 외부 API 스팬
```

`docker-compose.yml` 의 app 서비스에 걸어둔 설정이 이걸 만든다.

| 환경변수 | 역할 |
|---|---|
| `DD_TRACE_ENABLED=true` | 트레이싱 on |
| `DD_TRACE_SAMPLE_RATE=1.0` | 100% 수집 (트래픽 적은 학습 환경) |
| `DD_LOGS_INJECTION=true` | 로그에 `dd.trace_id` 주입 → 로그↔트레이스 점프 |
| `DD_DBM_PROPAGATION_MODE=full` | APM 스팬 ↔ DBM 쿼리 연결 |
| `DD_SERVICE_MAPPING=mysql:name-compat-db` | 서비스 맵에서 DB를 별도 노드로 |

### 확인 경로

| 보고 싶은 것 | Datadog UI |
|---|---|
| 요청 하나의 전체 흐름 | APM → Traces → `name-compat-api` → 트레이스 클릭 |
| 그 요청이 던진 SQL | 트레이스 안의 `pymysql.query` 스팬 → Tags의 `sql.query` |
| 이 요청이 남긴 로그 | 트레이스 상세 하단 **Logs** 탭 (trace_id로 자동 필터) |
| DB가 병목인지 | APM → Service Page → `name-compat-api` → Dependencies |
| 쿼리별 성능/실행계획 | Databases → `name-compat-db` (**DBM 필요**) |

### DB를 어디까지 볼 수 있나 — 3단계

| 단계 | 필요한 것 | 볼 수 있는 것 |
|---|---|---|
| **① DB 스팬** (이미 동작) | 없음. ddtrace 자동 계측 | 요청별 SQL, 쿼리 소요시간, N+1 발견 |
| **② RDS 메트릭** | `mysql.d/conf.yaml` 에 datadog 계정 채우기 | Connections, Slow_queries, InnoDB, 스키마 크기 |
| **③ DBM** | + RDS 파라미터 그룹 (`performance_schema=1` 등) + `dbm: true` | 쿼리별 실행시간 분포, 실행계획(EXPLAIN), 대기 이벤트 |

①은 지금 바로 보인다. ②는 `datadog/conf.d/mysql.d/conf.yaml` 상단 주석의 SQL을 실행하고
엔드포인트/비밀번호만 채우면 된다. ③은 파라미터 그룹을 새로 만들어 RDS를 재부팅해야
하므로, ②까지 확인한 뒤 여유 있을 때 붙이는 걸 권한다.

### 이 프로젝트에서 트레이스로 볼 만한 것

- `POST /api/compatibility` 는 계산(순수 CPU)과 `INSERT`(DB)가 한 트레이스에 같이 잡힌다.
  → 실제로 시간을 먹는 쪽이 DB라는 걸 눈으로 확인할 수 있다.
- `GET /api/fortune` 은 외부 API 스팬이 붙는다. 외부가 느려지면 트레이스 폭이 3초로 늘어난다.
- `DELETE /api/ranking` 는 단일 DELETE 스팬. 삭제 건수가 로그의 `@deleted` 에 남는다.

## 2. 로그 기반 커스텀 메트릭 (Logs → Generate Metrics)

앱이 남기는 JSON 로그를 그대로 메트릭으로 만들 수 있다.

| 메트릭 이름 | 쿼리 | 용도 |
|---|---|---|
| `namecompat.diagnosis.count` | `service:name-compat-api "compatibility.calculated"` | 진단 횟수 |
| `namecompat.diagnosis.score` | 위와 동일, measure = `@score` | 평균 궁합 점수 분포 |
| `namecompat.fortune.fallback` | `service:name-compat-api "fortune.opened" @source:fallback` | 외부 API 실패율 |
| `namecompat.validation.error` | `service:name-compat-api "compatibility.validation_failed"` | 입력 오류(=UX 문제) 추적 |
| `namecompat.db.save_failed` | `service:name-compat-api "db.save_result_failed"` | DB 저장 실패 |
| `namecompat.ranking.deleted` | `service:name-compat-api "ranking.deleted*"`, measure = `@deleted` | 삭제 건수 |

## 3. 모니터 정의

### 3-1. 서비스 다운
```
service check: http_check.status
  over: instance:name-compat-health
  alert if CRITICAL for 2 consecutive checks
```
> 메시지 예: `名前相性診断が応答していません @slack-my-channel`

### 3-2. 앱 에러율
```
avg(last_5m):
  ( sum:trace.flask.request.errors{service:name-compat-api}.as_count()
    / sum:trace.flask.request.hits{service:name-compat-api}.as_count() ) * 100
> 5      (warning: 2)
```

### 3-3. 응답시간 (p95)
```
avg(last_10m): p95:trace.flask.request.duration{service:name-compat-api} > 1
```

### 3-4. DB 쿼리 지연
```
avg(last_10m): p95:trace.pymysql.query.duration{service:name-compat-api} > 0.5
```

### 3-5. EC2 리소스
```
avg(last_10m): avg:system.cpu.user{host:hyojin-ubuntu} > 80
avg(last_5m):  avg:system.mem.pct_usable{host:hyojin-ubuntu} < 0.15
avg(last_5m):  avg:system.disk.in_use{host:hyojin-ubuntu,device:/dev/root} > 0.85
```

### 3-6. RDS
```
avg(last_10m): avg:aws.rds.cpuutilization{dbinstanceidentifier:hyojin-db} > 80
avg(last_10m): avg:aws.rds.database_connections{dbinstanceidentifier:hyojin-db} > 40
avg(last_15m): avg:aws.rds.free_storage_space{dbinstanceidentifier:hyojin-db} < 2000000000
```

### 3-7. 외부 API 열화 (fallback 비율)
```
sum(last_15m): sum:namecompat.fortune.fallback{*}.as_count() > 10
```
> 외부 API가 죽어도 서비스는 살아있지만, "왜 메시지가 단조로운가"를 설명해준다.

## 4. 대시보드 위젯 구성 (권장 순서)

1. **Top row (Status)** — http_check 상태, 오늘 진단 횟수, 평균 점수
2. **Application** — Requests/s, Error rate, Latency p50/p95/p99 (APM)
3. **Trace** — Service Map (api → db → external), 느린 트레이스 목록
4. **Nginx** — Requests/s, Active connections, 상태코드별 로그 카운트
5. **EC2** — CPU / Memory / Disk / Network
6. **RDS** — CPU, Connections, Free storage, Slow queries
7. **Business** — 점수 분포 히스토그램, 입력 오류(validation_failed) 추이
8. **External** — Fortune API 응답시간(로그의 `duration_ms`), fallback 카운트

## 5. 실습 시나리오 (일부러 장애를 만들어 본다)

| 시나리오 | 방법 | 확인할 것 |
|---|---|---|
| 앱 다운 | `docker compose stop app` | http_check CRITICAL, Nginx 502 급증 |
| DB 다운 | RDS 보안그룹에서 3306 인바운드 삭제 | `db.save_result_failed` 로그, `/api/health` degraded, 트레이스에 DB 스팬 에러 |
| 외부 API 장애 | `.env`의 `FORTUNE_API_URL`을 잘못된 값으로 변경 후 `--force-recreate app` | `fortune.api_failed` 로그, fallback 메트릭 상승 |
| DB 지연 | `SELECT SLEEP(3)` 를 던져보기 | 트레이스에서 pymysql 스팬이 늘어나는 것 |
| 부하 | `ab -n 2000 -c 50 http://localhost/api/ranking` | p95 latency, Nginx 429(rate limit), EC2 CPU |

각 시나리오 후 **APM → Traces**에서 해당 시간대 트레이스를 열어보면,
어느 스팬에서 시간이 늘어났는지 / 어디서 에러가 났는지가 색으로 표시된다.
이게 Observability 학습의 핵심 지점이다.
