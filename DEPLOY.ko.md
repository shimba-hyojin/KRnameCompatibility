**한국어** | [日本語](DEPLOY.md)

# AWS 배포 가이드

EC2 + Nginx + Docker + RDS + Datadog. 위에서부터 순서대로 따라가면 된다.
리전은 `ap-northeast-1`(도쿄) 기준. 예상 비용은 t3.micro + db.t4g.micro 조합으로 월 20~30 USD
(프리티어 적용 시 거의 0).

**실제 구축된 리소스**

| 종류 | 이름 |
|---|---|
| EC2 | `hyojin-ubuntu` (Ubuntu 24.04, t3.micro) |
| EC2 보안 그룹 | `hyojin-ubuntu-sg` |
| RDS | `hyojin-db` (MySQL 8.0, db.t4g.micro) |
| RDS 보안 그룹 | `hyojin-db-sg` |
| 키 페어 | `hyojin-key.pem` |
| 초기 데이터베이스 | `namecompat` |

---

## 0. 전체 구성

```
                    Internet
                       │
                  (80 / 443)
                       ▼
        ┌──────────────────────────────┐
        │  EC2  (Ubuntu 24.04, t3.micro)│
        │                              │
        │  ┌────────┐   ┌────────────┐  │
        │  │ Nginx  │──▶│ Flask app  │  │   Docker Compose
        │  │ :80    │   │ :8000      │  │
        │  └────────┘   └─────┬──────┘  │
        │  ┌──────────────────┴───────┐ │
        │  │  Datadog Agent           │ │
        │  └──────────────────────────┘ │
        └──────────────┬───────────────┘
                       │ 3306 (VPC 내부만)
                       ▼
              ┌─────────────────┐         ┌──────────────────┐
              │ RDS for MySQL   │         │ Fortune API      │
              │ db.t4g.micro    │         │ jugemkey.jp      │
              └─────────────────┘         └──────────────────┘
```

핵심 원칙 두 가지:

1. **RDS는 퍼블릭 액세스를 끈다.** EC2의 보안 그룹만 3306을 허용한다.
2. **앱 컨테이너는 포트를 외부에 열지 않는다.** Nginx만 80/443을 갖는다.

---

## 1. 보안 그룹 먼저 만들기

리소스보다 보안 그룹을 먼저 만들면 나중에 헤매지 않는다.

### 1-1. `hyojin-ubuntu-sg` (EC2용)

EC2 인스턴스 시작 화면의 "네트워크 설정 → 편집 → 보안 그룹 생성"에서 규칙까지 한 번에 만들 수 있다.

| 방향 | 타입 | 포트 | 소스 | 설명 |
|---|---|---|---|---|
| 인바운드 | SSH | 22 | **내 IP** | 0.0.0.0/0 절대 금지 |
| 인바운드 | HTTP | 80 | (1-3 참고) | 회사 정책에 따라 다름 |
| 아웃바운드 | 전체 | 전체 | 0.0.0.0/0 | 외부 API·Datadog·apt |

### 1-2. `hyojin-db-sg` (RDS용) — **RDS 생성 화면에서 만든다**

| 방향 | 타입 | 포트 | 소스 |
|---|---|---|---|
| 인바운드 | MYSQL/Aurora | 3306 | **`hyojin-ubuntu-sg`** (보안 그룹 참조) |

소스에 IP가 아니라 **보안 그룹 ID를 넣는 것**이 포인트다. EC2를 교체해도 규칙을 고칠 필요가 없다.

단, 이 규칙은 `hyojin-ubuntu-sg`가 이미 존재해야 넣을 수 있다. 순서는 이렇게 한다:

1. EC2를 먼저 만들어 `hyojin-ubuntu-sg`를 생성한다 → 3장
2. RDS 생성 화면의 "연결" 섹션에서 **VPC 보안 그룹 → 새로 생성**, 이름 `hyojin-db-sg`
3. RDS 생성이 끝난 뒤 `hyojin-db-sg`의 인바운드 규칙을 위 표대로 추가한다

> **함정**: RDS 생성 화면에서 SG를 새로 만들면 AWS가 자동으로 "내 노트북의 공인 IP/32"를
> 인바운드에 넣는다. 이 규칙은 퍼블릭 액세스가 꺼진 RDS에서는 아무 역할도 못 하고,
> EC2(사설 IP)에서 오는 트래픽과도 맞지 않아 타임아웃이 난다. **지우고 SG 참조로 교체한다.**

### 1-3. 사내 계정에서 `0.0.0.0/0`이 자동 삭제되는 경우

많은 회사가 보안 도구(AWS Config / Security Hub / 자체 remediation Lambda)로
**광범위 CIDR 인바운드 규칙을 자동 회수**한다. 1-1의 `HTTP 80 ← 0.0.0.0/0` 규칙이
추가 직후 사라졌다면 정책이 정상 동작한 것이다. 우회하지 말고 아래 중 하나를 쓴다.

#### 방법 A. SSH 포트 포워딩 ← **이 프로젝트의 채택 방식**

혼자 보거나 화면 공유로 보여주는 용도라면 80을 열 필요가 전혀 없다.
SSH 터널로 로컬에 끌어오면 브라우저에서는 그냥 로컬 사이트처럼 보인다.

`~/.ssh/config` 에 한 번만 등록해두면 명령이 짧아진다.

```sshconfig
Host nc
    HostName <EC2_PUBLIC_IP>
    User ubuntu
    IdentityFile ~/.ssh/hyojin-key.pem
    LocalForward 8888 localhost:80
    ServerAliveInterval 30
    ServerAliveCountMax 3
```

이후:

```bash
ssh nc                    # 터널 + 셸 동시에
ssh -fN nc                # 터널만 백그라운드로
```

브라우저에서 `http://localhost:8888` 접속.
Nginx·Flask·RDS·Datadog 전부 정상 동작하며, 외부에서 접근 가능한 포트는 하나도 없다.

> 포트가 이미 사용 중이면 `bind: Address already in use` 가 난다.
> `lsof -i :8888` 로 확인하거나 다른 포트를 쓴다.

터널이 끊기면 브라우저가 연결 거부를 낸다. `ssh nc`를 다시 실행하면 된다.
자주 끊긴다면 `brew install autossh` 후 `autossh -M 0 -fN nc`.

#### 방법 B. 회사 IP 대역으로 좁히기

사내에서만 쓸 서비스라면 소스를 회사 이그레스 CIDR로 지정한다.
정확한 대역은 네트워크/IT 팀에 문의한다.

#### 방법 C. SSM Session Manager (인바운드 22도 불필요)

가장 정책 친화적인 방법. Ubuntu AMI에는 SSM Agent가 이미 들어 있다.

1. EC2에 `AmazonSSMManagedInstanceCore` 정책을 가진 IAM 역할을 연결
2. 로컬에서:

```bash
aws ssm start-session --target <INSTANCE_ID> \
  --document-name AWS-StartPortForwardingSession \
  --parameters 'portNumber=80,localPortNumber=8888'
```

#### 방법 D. 동료에게 공개해야 할 때

일본 동료가 실제로 쓰게 하려면 사내에서 승인된 공개 경로가 필요하다.
보통 **내부 ALB + 사내 네트워크/VPN**, 또는 회사가 운영하는 리버스 프록시에 등록하는 방식이다.
이건 보안/인프라 팀과 상의해야 하는 항목이고, 임의로 SG를 열어 해결할 문제가 아니다.

---

## 2. RDS for MySQL 생성

콘솔 → RDS → 데이터베이스 생성. 적지 않은 항목은 기본값 그대로 둔다.

| 섹션 | 항목 | 값 |
|---|---|---|
| ① | 생성 방식 | **표준 생성** (손쉬운 생성은 SG/초기DB 지정 불가) |
| ② | 엔진 | MySQL 8.0.x |
| ③ | 템플릿 | 프리 티어 (없으면 개발/테스트 + db.t4g.micro) |
| ④ | DB 인스턴스 식별자 | `hyojin-db` |
| ④ | 마스터 사용자 | `admin` |
| ④ | 마스터 암호 | 직접 입력 → **따로 보관** |
| ⑤ | 인스턴스 클래스 | db.t4g.micro |
| ⑥ | 스토리지 | gp3 20GB, **자동 조정 체크 해제** (과금 사고 방지) |
| ⑦ | 퍼블릭 액세스 | **아니요** |
| ⑦ | VPC 보안 그룹 | **새로 생성** → 이름 `hyojin-db-sg` |
| ⑧ | **초기 데이터베이스 이름** | `namecompat` ← **추가 구성 안에 숨어 있음** |
| ⑧ | 백업 보존 기간 | 1일 (학습용) |

⑧을 비워두면 빈 서버만 생기고 나중에 직접 `CREATE DATABASE` 해야 한다.

생성 후 **엔드포인트**를 복사해 둔다 (연결 & 보안 탭).
예: `hyojin-db.c1mmuwo2mx97.ap-northeast-1.rds.amazonaws.com`

상태가 `생성 중` → `백업 중` → **`사용 가능`** 이 되기까지 10~15분. 그동안 3장을 진행한다.

### 2-1. 문자셋 확인

한글/일본어를 안전하게 저장하려면 utf8mb4가 필요하다. RDS MySQL 8.0은 기본이 utf8mb4다.

```sql
SHOW VARIABLES LIKE 'character_set_server';   -- utf8mb4 기대
SHOW VARIABLES LIKE 'collation_server';
```

---

## 3. EC2 인스턴스 생성

| 섹션 | 항목 | 값 |
|---|---|---|
| ① | 이름 | `hyojin-ubuntu` |
| ② | AMI | Ubuntu Server 24.04 LTS, **64비트(x86)** |
| ③ | 인스턴스 유형 | t3.micro |
| ④ | 키 페어 | **새 키 페어 생성** → `hyojin-key`, RSA, `.pem` |
| ⑤ | 퍼블릭 IP 자동 할당 | 활성화 |
| ⑤ | 방화벽 | 보안 그룹 생성 → `hyojin-ubuntu-sg` (규칙은 1-1) |
| ⑥ | 스토리지 | **20 GiB** gp3 (기본 8GiB는 Docker 이미지로 금방 찬다) |
| ⑦ | | 인스턴스 시작 |

> **키 페어는 딱 한 번만 다운로드된다.** 잃어버리면 이 인스턴스에 영구히 접속할 수 없다.
> 받은 즉시 안전한 곳으로 옮긴다.

### 3-1. 접속

```bash
mv ~/Downloads/hyojin-key.pem ~/.ssh/
chmod 400 ~/.ssh/hyojin-key.pem
ssh -i ~/.ssh/hyojin-key.pem ubuntu@<EC2_PUBLIC_IP>
```

프롬프트가 `ubuntu@ip-172-31-x-x:~$` 로 바뀌면 성공.

**자주 나는 에러**

| 메시지 | 원인 |
|---|---|
| `Permission denied (publickey)` | `-i` 를 안 붙였거나 키 경로가 틀림. Ubuntu 사용자명은 `ubuntu` (ec2-user 아님) |
| `Identity file ... No such file` | 키가 아직 Downloads에 있음 → `mv` |
| `UNPROTECTED PRIVATE KEY FILE` | `chmod 400` 안 함 |
| `Connection timed out` | SSH 22 소스가 현재 IP와 다름 → 보안 그룹 갱신 |

> IP가 재부팅마다 바뀌는 게 싫으면 Elastic IP를 할당한다 (연결된 상태로 쓰면 무료).

---

## 4. EC2 기본 세팅

```bash
sudo apt update && sudo apt upgrade -y
sudo timedatectl set-timezone Asia/Tokyo
sudo apt install -y git curl vim mysql-client-core-8.0
```

`apt upgrade` 중 파란 화면(서비스 재시작 확인)이 뜨면 Enter.

### 4-0. 스왑 추가 — t3.micro에서는 사실상 필수

t3.micro는 메모리가 약 950MB뿐이다. Datadog Agent(200~300MB)를 띄운 상태에서
`ddtrace` 같은 C 확장 패키지를 빌드하면 메모리가 모자라 **빌드가 멈춘다**
(에러도 안 나고 pip 다운로드 중간에 그냥 정지). 스왑을 미리 붙여두면 이 문제가 없다.

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -m        # Swap: 2047 확인
```

`/etc/fstab`에 등록했으므로 재부팅 후에도 유지된다.

빌드가 여전히 무겁다면 Agent를 잠시 끄고 빌드한다:

```bash
docker compose stop datadog
docker compose build app
docker compose up -d
docker compose --profile datadog up -d
```

### 4-1. Docker / Docker Compose 설치

```bash
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io \
                    docker-buildx-plugin docker-compose-plugin

# sudo 없이 docker 쓰기 (재로그인 필요)
sudo usermod -aG docker ubuntu
exit
```

**맥으로 나갔다가** 다시 접속해서 확인한다 (EC2 안에서 ssh를 다시 걸면 안 된다):

```bash
ssh -i ~/.ssh/hyojin-key.pem ubuntu@<EC2_PUBLIC_IP>
docker run --rm hello-world     # sudo 없이 되어야 성공
```

> 지금 어디 있는지 헷갈리면 `hostname`. `ip-172-31-...` 이면 EC2 안이다.

---

## 5. RDS 연결 확인

EC2에서 RDS로 붙어본다. 여기서 막히면 **보안 그룹**이나 **VPC**를 다시 본다.

```bash
# 포트만 빠르게 확인 (mysql 클라이언트 없이)
timeout 5 bash -c "cat < /dev/null > /dev/tcp/<RDS_ENDPOINT>/3306" \
  && echo "3306 열림" || echo "막힘"

# DNS가 사설 IP로 풀리는지 (172.31.x.x 이어야 정상)
getent hosts <RDS_ENDPOINT>

mysql -h <RDS_ENDPOINT> -u admin -p -e "SHOW DATABASES;"
```

`namecompat`이 목록에 있으면 통과.

| 증상 | 원인 |
|---|---|
| 멈춘 뒤 `ERROR 2003 ... (110)` | 타임아웃. `hyojin-db-sg`에 3306 규칙 없음 또는 소스가 SG 참조가 아님 |
| `Access denied` | 암호 틀림 |
| `Unknown MySQL server host` | 엔드포인트 오타 |
| 공인 IP로 풀림 | EC2와 RDS가 다른 VPC |

### 5-1. 앱 전용 계정 (선택)

첫 기동은 `admin`으로 하는 편이 편하다 (앱이 테이블을 자동 생성하려면 DDL 권한 필요).
정상 동작을 확인한 뒤 권한을 좁힌다.

```sql
CREATE USER 'appuser'@'%' IDENTIFIED BY '<APP_DB_PASSWORD>';
GRANT SELECT, INSERT, UPDATE, DELETE ON namecompat.* TO 'appuser'@'%';
FLUSH PRIVILEGES;
```

삭제 기능(`DELETE /api/ranking`)을 쓰려면 `DELETE` 권한이 필요하다.

---

## 6. 애플리케이션 배포

### 6-1. 코드 업로드

git 저장소가 있으면 `git clone`, 없으면 로컬에서 압축해서 보낸다.

```bash
# 맥에서
cd ~/Downloads
scp -i ~/.ssh/hyojin-key.pem name-compat.tar.gz ubuntu@<EC2_IP>:~/

# EC2에서
cd ~
tar -xzf name-compat.tar.gz
cd name-compat
chmod -R a+rX . && chmod 600 .env    # ← 아래 주의 참고
```

> **권한 주의**: 정적 파일이 `600`(소유자만 읽기)이면 nginx 워커(uid 101)가 읽지 못해
> `/` 가 **404** 로 나온다 (403이 아니라 404인 게 이 증상의 특징). `chmod -R a+rX` 필수.

> **재배포 시**: 아카이브의 `.env`는 로컬용 기본값(`DB_HOST=mysql`)이므로 덮어쓰면 DB가 끊긴다.
> ```bash
> cp name-compat/.env /tmp/env.bak
> tar -xzf name-compat.tar.gz
> cp /tmp/env.bak name-compat/.env
> ```

### 6-2. `.env` 작성

```bash
nano .env
```

운영에서 고칠 항목:

```ini
APP_ENV=prod
DB_HOST=hyojin-db.c1mmuwo2mx97.ap-northeast-1.rds.amazonaws.com
DB_USER=admin
DB_PASSWORD=<RDS 마스터 암호>

DD_API_KEY=<DATADOG_API_KEY>
DD_TRACE_ENABLED=true
```

`DB_PORT=3306`, `DB_NAME=namecompat` 는 그대로. nano 저장은 `Ctrl+O` → Enter → `Ctrl+X`.

```bash
chmod 600 .env
grep -E "^(APP_ENV|DB_HOST|DB_USER|DB_NAME)=" .env    # 확인
```

> `.env` 변경은 컨테이너 **재생성**이 필요하다. `restart`로는 환경변수가 안 바뀐다.
> `docker compose up -d --force-recreate app`

### 6-3. 기동

```bash
docker compose up -d --build
docker compose ps
```

`namecompat-app`, `namecompat-nginx` 둘 다 `Up`이면 된다.
`namecompat-mysql`은 `local` 프로파일이라 안 뜨는 게 정상 (RDS를 쓰므로).

t3.micro에서 이미지 빌드에 2~4분 걸린다.

### 6-4. 동작 확인

```bash
curl -i localhost/api/health
```

기대값:

```json
{"db":"ok","env":"prod","status":"ok"}
```

`"db":"ok"` 가 핵심이다. 이게 나오면 EC2 → RDS 경로까지 다 살아있다.

```bash
curl -s -X POST localhost/api/compatibility \
  -H 'Content-Type: application/json' \
  -d '{"partner_name":"야마다"}' | head -c 250
curl -s localhost/api/ranking
curl -s localhost/api/fortune
```

야마다는 **93%** 가 나와야 맞다 (알고리즘이 고정값이므로 로컬 테스트와 동일).

DB에 실제로 들어갔는지:

```bash
source .env
mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASSWORD" namecompat \
  -e "SELECT partner_name, score, grade_label, lookup_count FROM compatibility_results;"
```

### 6-5. 브라우저에서 보기

1-3 방법 A의 SSH 터널을 쓴다.

```bash
# 맥 터미널에서
ssh -i ~/.ssh/hyojin-key.pem -L 8888:localhost:80 ubuntu@<EC2_IP>
```

터널 창을 열어둔 채 브라우저 → `http://localhost:8888`

---

## 7. HTTPS 적용 (도메인이 있을 때)

도메인 A 레코드를 EC2의 Elastic IP로 향하게 한 뒤:

```bash
sudo apt install -y certbot
docker compose stop nginx          # 80 포트를 잠시 비워준다

sudo certbot certonly --standalone -d namecompat.example.com

# docker-compose.yml 의 nginx 볼륨에서 letsencrypt 주석을 해제
vim docker-compose.yml
```

`nginx/default.conf` 에 443 서버 블록을 추가한다:

```nginx
server {
    listen 443 ssl;
    http2 on;
    server_name namecompat.example.com;

    ssl_certificate     /etc/letsencrypt/live/namecompat.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/namecompat.example.com/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_session_cache   shared:SSL:10m;
    add_header Strict-Transport-Security "max-age=31536000" always;

    root /usr/share/nginx/html;
    index index.html;

    # 이하 location 블록은 80 서버 블록과 동일하게 복사
}
```

그리고 80 서버 블록의 `return 301 https://$host$request_uri;` 주석을 해제한다.

```bash
docker compose up -d nginx

# 자동 갱신 (매월 1일 03:00)
sudo crontab -e
# 0 3 1 * * certbot renew --quiet --pre-hook "docker compose -f /home/ubuntu/name-compat/docker-compose.yml stop nginx" --post-hook "docker compose -f /home/ubuntu/name-compat/docker-compose.yml start nginx"
```

---

## 8. Datadog 연동

### 8-1. Agent 기동 (컨테이너 방식)

`.env`에 `DD_API_KEY`를 넣었으면 프로파일만 추가하면 된다.

```bash
docker compose --profile datadog up -d
docker compose exec datadog agent status
```

Datadog UI → Infrastructure → Host Map 에 `hyojin-ubuntu`가 뜨면 성공 (2~3분 소요).

수집되는 것:

- **EC2 메트릭**: CPU / Memory / Disk / Network (system check)
- **컨테이너 로그**: `DD_LOGS_CONFIG_CONTAINER_COLLECT_ALL=true`
- **Nginx**: 컨테이너 라벨의 Autodiscovery로 `stub_status` + access/error log
- **APM + DB 스팬**: `ddtrace-run` 이 Flask와 pymysql을 자동 계측

### 8-2. MySQL / RDS 연동

```bash
nano datadog/conf.d/mysql.d/conf.yaml   # <RDS_ENDPOINT>, 비밀번호 채우기
docker compose restart datadog
docker compose exec datadog agent check mysql
```

파일 상단 주석에 datadog 계정 생성 SQL과 DBM용 파라미터 그룹 설정이 정리되어 있다.

추가로 **AWS Integration**을 붙이면 CloudWatch의 RDS 메트릭
(`aws.rds.cpuutilization`, `aws.rds.free_storage_space` 등)까지 들어온다.
Datadog UI → Integrations → Amazon Web Services → IAM Role 방식으로 연결.

### 8-3. 로그 파이프라인

앱은 JSON 한 줄 로그를 stdout으로 낸다.

```json
{"timestamp":"2026-09-03T10:12:33+00:00","status":"info","logger":"app",
 "message":"compatibility.calculated","service":"name-compat-api","env":"prod",
 "partner_name":"야마다","score":93,"grade":"運命級","saved":true,
 "dd.trace_id":"...","dd.span_id":"..."}
```

Datadog Log Explorer에서 `service:name-compat-api @score:>90` 처럼 바로 검색된다.
`dd.trace_id`가 들어 있어 로그 ↔ APM 트레이스가 서로 연결된다.

모니터/대시보드/트레이스 구성은 [`datadog/monitors.md`](datadog/monitors.ko.md)에 정리했다.

---

## 9. 운영 명령 모음

```bash
# 상태
docker compose ps
docker compose logs -f app          # 앱 로그
docker compose logs --tail=30 nginx # Nginx 로그
docker compose exec datadog agent status

# 배포 (코드 갱신)
docker compose up -d --build app
docker compose exec nginx nginx -t   # 설정 문법 검사
docker compose exec nginx nginx -s reload

# nginx 설정만 바꿨을 때
docker compose up -d --force-recreate nginx

# 재시작 / 정지
docker compose restart app
docker compose down                  # 컨테이너 삭제 (볼륨 유지)

# 디스크 정리 (EC2 20GB는 금방 찬다)
docker system prune -af --volumes
```

---

## 10. 트러블슈팅

실제로 겪은 것들을 우선순위 순으로.

| 증상 | 확인할 것 |
|---|---|
| **`docker compose build` 가 pip 다운로드 중 멈춤** | 메모리 부족. `free -m` 의 `available` 이 100MB 미만이면 4-0의 스왑 추가 |
| **`/` 가 404** (API는 정상) | 정적 파일 권한. nginx 워커(uid 101)가 못 읽는 상태 → `chmod -R a+rX ~/name-compat && chmod 600 ~/name-compat/.env` |
| **nginx가 Started 직후 죽음** | `docker compose logs nginx`. `log_format`은 `http` 컨텍스트 전용 — `server` 블록에 넣으면 기동 실패. `00-upstream.conf`에 둔다 |
| **`curl localhost` 연결 거부** | nginx 컨테이너가 죽은 것. 위 항목 확인 |
| **RDS 타임아웃 (`2003 ... (110)`)** | `hyojin-db-sg` 인바운드에 3306/SG참조 규칙이 있는지. AWS가 자동 추가한 `내IP/32`만 있으면 안 된다 |
| **`/api/health` 가 `db:down`** | `.env`의 `DB_HOST`가 아직 `mysql`(로컬 기본값)일 수 있다. 고친 뒤 `--force-recreate app` |
| **SSH `Permission denied (publickey)`** | `-i` 누락, 키 경로 오류, 또는 EC2 안에서 실행 중 (`hostname` 확인) |
| **`bind: Address already in use`** | 터널 포트 충돌. `lsof -i :8888` 또는 다른 포트 사용 |
| **80 규칙이 자동 삭제됨** | 회사 보안 도구. 1-3절의 SSH 터널로 전환 |
| DB 저장은 실패하는데 점수는 나옴 | 의도된 동작(graceful degradation). `db.save_result_failed` 로그 확인 |
| 한글이 `???` 로 저장됨 | 테이블/컬럼 charset이 utf8mb4인지 |
| 포춘쿠키가 `オフラインメッセージ` | 외부 API 실패 → fallback. `fortune.api_failed` 로그 확인 |
| Datadog에 호스트가 안 뜸 | `DD_API_KEY`, `DD_SITE`(EU는 datadoghq.eu), 아웃바운드 443 |
| APM 트레이스 없음 | `DD_TRACE_ENABLED=true`, `DD_AGENT_HOST=datadog`, CMD가 `ddtrace-run` |
| 429 Too Many Requests | Nginx rate limit. `00-upstream.conf`의 `rate=10r/s` 조정 |
| 디스크 풀 | `docker system prune -af` |

---

## 11. 다음 단계 (학습 확장용)

- **CI/CD**: GitHub Actions → ECR 푸시 → EC2에서 `docker compose pull && up -d`
- **ALB + ACM**: certbot 대신 ALB에서 TLS 종료, 헬스체크는 `/api/health`
- **Auto Scaling**: 앱이 stateless이므로 EC2 2대 + ALB로 바로 확장 가능
- **Datadog Synthetics**: 도쿄/서울 리전에서 실제 브라우저 테스트
- **RDS Multi-AZ**: 장애 조치 실습
- **Secrets Manager**: `.env` 제거
