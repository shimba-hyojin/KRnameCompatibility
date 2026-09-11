**한국어** | [日本語](README.md)

# 韓国式 名前相性診断 (name-compat)

한국의 이름 궁합점(이름궁합)을 일본인 동료가 설명 없이 즐길 수 있게 만든 작은 웹 서비스.
본인 이름은 **심효진**으로 고정되고, 사용자는 상대방 이름만 한글로 입력한다.

실제 목적은 AWS + Observability 학습이다. Linux · EC2 · Nginx · Docker · Flask · MySQL(RDS)
· 외부 API 연동 · HTTPS · 보안 그룹 · 로깅 · 모니터링 · Datadog을 하나의 서비스에서 다룬다.

**현재 배포 상태**: EC2(`hyojin-ubuntu`) + RDS(`hyojin-db`, 도쿄 리전).
회사 보안 정책상 80 포트를 외부에 열 수 없으므로 SSH 터널로 접근한다 → `DEPLOY.md` 1-3절.

---

## 빨리 보기

의존성 설치 없이 UI만 확인:

```bash
open preview.html          # macOS
```

의존성 설치 없이 API까지 확인 (표준 라이브러리만 사용):

```bash
cd backend && python3 devserver.py     # http://localhost:8080
```

Docker로 전체 스택 (MySQL 포함):

```bash
cp .env.example .env
docker compose --profile local up -d --build
open http://localhost
```

EC2에 배포된 것을 보기 (SSH 터널):

```bash
ssh -i ~/.ssh/hyojin-key.pem -L 8888:localhost:80 ubuntu@<EC2_IP>
# 터널 열어둔 채 http://localhost:8888
```

---

## 디렉터리 구조

```
name-compat/
├── README.md                    이 문서 (설계 확정 내용 포함)
├── DEPLOY.md                    AWS 배포 가이드 (EC2/RDS/보안그룹/HTTPS/Datadog)
├── docker-compose.yml           app + nginx + mysql(local) + datadog
├── .env                         실제 환경변수 (git 제외)
├── .env.example                 환경변수 템플릿
├── preview.html                 서버 없이 UI 확인용 (자동 생성물)
│
├── backend/
│   ├── app.py                   Flask 앱 · 라우팅 · 에러 핸들링
│   ├── wsgi.py                  gunicorn 엔트리포인트
│   ├── config.py                환경변수 설정
│   ├── hangul.py                자모 분해 + 획수표 (알고리즘 확정 지점)
│   ├── compatibility.py         궁합 알고리즘 + 계산 과정 생성
│   ├── db.py                    MySQL(RDS) 접근 (저장/랭킹/삭제)
│   ├── fortune.py               외부 Fortune API 연동 + fallback
│   ├── logging_setup.py         JSON 구조화 로깅 (Datadog 연동)
│   ├── devserver.py             의존성 없는 개발 서버
│   ├── gunicorn.conf.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── tests/test_core.py       단위 테스트
│
├── frontend/
│   ├── index.html               일본어 UI
│   ├── css/style.css
│   └── js/
│       ├── app.js               API 호출 · 결과 렌더링 · 계산 과정 · 삭제
│       └── kana2hangul.js       カタカナ → ハングル 변환 (일본인용 입력 보조)
│
├── nginx/
│   ├── 00-upstream.conf         upstream + rate limit + log_format (http 컨텍스트)
│   └── default.conf             reverse proxy + static + JSON access log
│
├── db/init.sql                  스키마
├── datadog/
│   ├── conf.d/nginx.d/conf.yaml
│   ├── conf.d/mysql.d/conf.yaml.example  ← 복제해서 conf.yaml 생성 (git 제외)
│   ├── conf.d/http_check.d/conf.yaml
│   └── monitors.md              모니터/대시보드/트레이스 설계
└── tools/
    ├── mock-api.js              preview용 모의 API
    └── build_preview.py         preview.html 생성 스크립트
```

---

## 확정된 알고리즘 (설계서 6.3 / 6.4)

계산 방식이 여러 갈래인 영역이므로, **이 프로젝트의 규칙을 한 곳에 고정**했다.
표는 `backend/hangul.py`에만 존재하고 모든 계산이 이를 참조한다.
따라서 동일 입력은 항상 동일 결과를 낸다.

### 획수표

**자음**

| ㄱ | ㄴ | ㄷ | ㄹ | ㅁ | ㅂ | ㅅ | ㅇ | ㅈ | ㅊ | ㅋ | ㅌ | ㅍ | ㅎ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 | 2 | 3 | 5 | 4 | 4 | 2 | 1 | 3 | 4 | 3 | 4 | 4 | 3 |

**모음**

| ㅏ | ㅐ | ㅑ | ㅒ | ㅓ | ㅔ | ㅕ | ㅖ | ㅗ | ㅘ | ㅙ | ㅚ | ㅛ | ㅜ | ㅝ | ㅞ | ㅟ | ㅠ | ㅡ | ㅢ | ㅣ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 | 3 | 3 | 4 | 2 | 3 | 3 | 4 | 2 | 4 | 5 | 3 | 3 | 2 | 4 | 5 | 3 | 3 | 1 | 2 | 1 |

**겹자음·겹받침**은 구성 자음의 합으로 정의한다.
`ㄲ=4, ㄸ=6, ㅃ=8, ㅆ=4, ㅉ=6` / `ㄳ=4, ㄵ=5, ㄶ=5, ㄺ=7, ㄻ=9, ㄼ=9, ㄽ=7, ㄾ=9, ㄿ=9, ㅀ=8, ㅄ=6`

### 계산 순서

```
STEP 1  음절 → 초성/중성/종성 분해, 음절별 획수 합
        심효진 → 심(ㅅ2+ㅣ1+ㅁ4=7) 효(ㅎ3+ㅛ3=6) 진(ㅈ3+ㅣ1+ㄴ2=6) = [7, 6, 6]
        야마다 → [4, 6, 5]

STEP 2  두 배열을 교차 병합 (항상 심효진이 먼저)
        [7, 4, 6, 6, 6, 5]
        길이가 다르면 짧은 쪽이 끝난 뒤 남은 값을 순서대로 뒤에 붙인다.

STEP 3  인접한 두 수를 더하고 10 이상이면 일의 자리만 남긴다. 길이 2까지 반복.
        [7, 4, 6, 6, 6, 5]
        [1, 0, 2, 2, 1]
        [1, 2, 4, 3]
        [3, 6, 7]
        [9, 3]

STEP 4  남은 두 수를 십의 자리/일의 자리로 읽는다 → 93%
```

계산의 모든 중간 단계는 API 응답의 `steps`에 담겨, 화면의 「どんな仕組み？」에서 그대로 보인다.

### 점수 구간

| 점수 | 등급 |
|---|---|
| 90+ | 運命級 |
| 80+ | 大吉 |
| 70+ | 吉 |
| 60+ | 中吉 |
| 50+ | 小吉 |
| 40+ | 末吉 |
| 20+ | がんばれ |
| 0+ | ドンマイ |

---

## 카타카나 입력 보조

일본인 사용자는 한글 키보드가 없다. 그래서 프론트엔드에
`カタカナ / ひらがな → ハングル` 변환기를 넣었다 (`frontend/js/kana2hangul.js`).
한국의 외래어 표기법에 가까운 규칙을 따른다.

| 입력 | 출력 | 적용 규칙 |
|---|---|---|
| たなか | 다나카 | カ·タ행은 어두에서 평음(가/다) |
| さとう | 사토 | 장모음(おう)은 표기하지 않음 |
| こんどう | 곤도 | ん → ㄴ 받침 + 장모음 생략 |
| はっとり | 핫토리 | っ → ㅅ 받침 |
| つじ | 쓰지 | つ는 항상 쓰 |
| ヒョウドウ | 효도 | 요음 + 장모음 생략 |

변환 결과는 사용자가 직접 수정할 수 있다. 최종 검증은 서버에서 다시 한다.

---

## API

| Method | Path | 설명 |
|---|---|---|
| GET | `/api/health` | 헬스체크 (DB 상태 포함) |
| GET | `/api/meta` | 본인 이름, 통계 |
| POST | `/api/compatibility` | 궁합 진단 |
| GET | `/api/ranking?limit=20` | 랭킹 (score DESC) |
| DELETE | `/api/ranking` | 랭킹 전체 삭제 |
| DELETE | `/api/ranking/{이름}` | 특정 이름의 기록 삭제 |
| GET | `/api/fortune` | 포춘쿠키 (외부 API) |
| GET | `/api/stroke-table` | 획수표 |

삭제 API는 `ADMIN_TOKEN` 환경변수가 설정되어 있으면 `X-Admin-Token` 헤더를 요구한다.
비어 있으면(기본) 무인증 — SSH 터널로만 접근하는 개인 환경 전제이므로, 외부에 공개할 때는
반드시 값을 채운다.

### POST /api/compatibility

```json
// Request
{ "partner_name": "야마다" }

// Response 200
{
  "owner_name": "심효진",
  "partner_name": "야마다",
  "score": 93,
  "grade": { "label": "運命級", "comment": "これはもう運命。..." },
  "steps": {
    "step1_decompose": {
      "owner":   [{ "char": "심", "strokes": 7,
                    "jamos": [{ "char": "ㅅ", "role": "chosung",
                                "role_label": "初声(子音)", "strokes": 2 }] }],
      "partner": []
    },
    "step2_strokes":     { "owner": [7, 6, 6], "partner": [4, 6, 5] },
    "step3_interleaved": [7, 4, 6, 6, 6, 5],
    "step4_reduction":   [[7,4,6,6,6,5], [1,0,2,2,1], [1,2,4,3], [3,6,7], [9,3]],
    "step5_score": 93
  },
  "saved": true
}
```

에러는 `400`과 함께 일본어 메시지를 준다.

```json
{ "error": "NOT_HANGUL", "message": "ハングル（한글）で入力してください。例: 야마다" }
```

`EMPTY` / `NOT_HANGUL` / `LENGTH` 세 종류이며, 완성형 한글 2~8자만 통과한다.

---

## 데이터베이스

```sql
compatibility_results
  id            BIGINT UNSIGNED PK
  owner_name    VARCHAR(20)      -- 심효진
  partner_name  VARCHAR(20)
  score         TINYINT UNSIGNED
  grade_label   VARCHAR(32)
  detail        JSON             -- 계산 과정 전체
  lookup_count  INT UNSIGNED     -- 조회 횟수
  created_at    DATETIME
  updated_at    DATETIME
  UNIQUE (owner_name, partner_name)
  KEY (score DESC, created_at ASC)
```

`(owner_name, partner_name)`에 UNIQUE를 두고 UPSERT한다.
같은 입력은 점수가 항상 같으므로 행이 늘어날 이유가 없고, 랭킹에 같은 사람이 중복 표시되지 않는다.
대신 `lookup_count`로 인기도를 센다.

---

## 장애 시 동작 (graceful degradation)

학습 프로젝트지만, 관찰할 만한 상태를 만들려면 실패 처리가 명확해야 한다.

| 실패 지점 | 서비스 동작 | 남는 신호 |
|---|---|---|
| RDS 다운 | 점수 계산·표시는 정상, 저장만 실패 (`saved: false`) | `db.save_result_failed` 로그, `/api/health` → `db: down` |
| RDS 다운 (랭킹) | 랭킹만 `503` | `ranking.query_failed` 로그 |
| 외부 Fortune API 다운/지연 | 3초 타임아웃 후 로컬 메시지로 대체 | `fortune.api_failed` 로그, 응답의 `source: "fallback"` |
| 앱 다운 | Nginx 502 | `http_check` CRITICAL |

---

## 로컬 개발

```bash
# 1) 코어 로직만 테스트
cd backend
python3 -m pytest -q

# 2) 의존성 없는 개발 서버 (랭킹은 메모리)
python3 devserver.py

# 3) Flask로 실행 (DB 없이)
pip install -r requirements.txt
DB_ENABLED=false python3 app.py

# 4) Docker 전체 스택
docker compose --profile local up -d --build

# 5) preview.html 재생성
python3 tools/build_preview.py
```

---

## GitHub Pages 정적판

서버 없이 브라우저만으로 도는 버전을 함께 제공한다. 동료에게 링크 하나로 공유할 때 쓴다.

```bash
python3 tools/build_static.py     # docs/index.html 생성
open docs/index.html              # 로컬 확인
```

궁합 알고리즘은 EC2판과 동일하게 구현되어 **점수가 항상 같다** (검증: 야마다 93%, 타나카 93%,
사토 36%, 스즈키 79%, 와타나베 62%, 이토 74%, 코바야시 68%).
차이는 랭킹 저장 위치뿐이다 — RDS(공유) vs localStorage(브라우저별).

공개 절차는 [`GITHUB_PAGES.md`](GITHUB_PAGES.ko.md)를 본다.

> **주의**: 비밀값이 들어가는 파일은 `.gitignore` 에 등록되어 있다.
> push 전에 `git status --short` 로 반드시 확인한다.
>
> | 파일 | 내용 | git |
> |---|---|---|
> | `.env` | Datadog API 키, RDS 비밀번호 | 제외 |
> | `datadog/conf.d/mysql.d/conf.yaml` | datadog DB 계정 비밀번호 | 제외 |
> | `datadog/conf.d/mysql.d/conf.yaml.example` | 플레이스홀더만 | 관리 |
> | `frontend/js/rum.js` 의 `clientToken` | 공개 전제 값 (`pub` 접두사) | 관리해도 됨 |

## CloudWatch와 비교

같은 EC2를 CloudWatch Agent와 Datadog Agent 양쪽으로 관측해서 차이를 확인하는 구성도 넣어뒀다.

```bash
# cloudwatch/amazon-cloudwatch-agent.json 을 EC2에 두고 기동
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config -m ec2 -s -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
```

CloudWatch는 기본적으로 **EC2 메모리를 주지 않는다.** Agent를 깔는 가장 큰 이유가 여기 있다.
절차와 비교 포인트는 [`CLOUDWATCH.ko.md`](CLOUDWATCH.ko.md)를 본다.

## 다음 단계

배포는 [`DEPLOY.ko.md`](DEPLOY.ko.md), 모니터링·트레이스 설계는
[`datadog/monitors.ko.md`](datadog/monitors.ko.md),
CloudWatch 비교는 [`CLOUDWATCH.ko.md`](CLOUDWATCH.ko.md)를 본다.
