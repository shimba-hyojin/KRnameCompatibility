**한국어** | [日本語](GITHUB_PAGES.md)

# GitHub Pages 공개 가이드

이 프로젝트를 GitHub에 올리고, 누구나 접속할 수 있는 웹페이지로 공개하는 절차.

---

## 0. 먼저 알아야 할 것

GitHub Pages는 **파일을 나눠주는 역할만** 합니다. Python을 실행해주는 서버가 없습니다.

| 구성 | GitHub Pages | 이유 |
|---|---|---|
| HTML / CSS / JS | ✅ | 브라우저가 실행 |
| Flask (Python) | ❌ | 실행할 서버가 없음 |
| RDS (MySQL) | ❌ | DB 접속 불가 |
| Nginx | 불필요 | GitHub이 대신 |

그래서 **정적판**을 따로 만들었습니다 (`docs/index.html`).

| 기능 | EC2판 | GitHub Pages판 |
|---|---|---|
| 궁합 계산 | Flask | **브라우저** (같은 알고리즘 → 같은 점수) |
| 카타카나 변환 | 브라우저 | 브라우저 (동일) |
| 계산 과정 표시 | ✅ | ✅ |
| 랭킹 저장 | RDS (모두 공유) | **localStorage** (접속자 각자) |
| 삭제 기능 | ✅ | ✅ (자기 브라우저 것만) |
| 포춘쿠키 | 외부 API + 폴백 | 로컬 메시지만 |
| Datadog 관측 | ✅ | ❌ (서버가 없음) |

**랭킹이 사람마다 다르게 보인다**는 게 가장 큰 차이입니다. 서버가 없으니 데이터를 모을 곳이 없습니다.

---

## 1. ⚠️ 올리기 전 필수 확인 — 비밀값

`.env` 에는 **Datadog API 키**와 **RDS 비밀번호**가 들어 있습니다.
GitHub에 공개되면 누구나 볼 수 있습니다.

`.gitignore` 에 이미 등록되어 있지만, 반드시 눈으로 확인하세요.

```bash
cd ~/name-compat        # 또는 로컬 프로젝트 폴더
cat .gitignore          # .env, *.pem 이 있어야 함
```

git 초기화 후에는 이렇게 확인합니다:

```bash
git status --short       # .env 가 목록에 없어야 정상
git check-ignore -v .env # ".gitignore:1:.env" 처럼 나오면 무시되는 중
```

> **만약 실수로 커밋했다면** 파일만 지워도 히스토리에 남습니다.
> 그때는 **즉시 키를 폐기하고 새로 발급**하는 게 유일한 해결책입니다.
> (Datadog: Organization Settings → API Keys / RDS: 마스터 암호 수정)

---

## 2. 정적판 생성

```bash
python3 tools/build_static.py
```

`docs/index.html` 과 `docs/.nojekyll` 이 만들어집니다.
프론트엔드를 고칠 때마다 이 명령을 다시 실행하면 됩니다.

로컬에서 미리 확인:

```bash
open docs/index.html      # macOS — 파일을 그냥 열어도 동작
```

---

## 3. GitHub 저장소 만들기

### 3-1. 웹에서 저장소 생성

github.com → 우측 상단 **+** → **New repository**

| 항목 | 값 |
|---|---|
| Repository name | `name-compat` |
| Description | 韓国式 名前相性診断 (Korean name compatibility) |
| 공개 범위 | **Public** ← Pages 무료 사용 조건 |
| Add a README | 체크 안 함 (이미 있음) |
| .gitignore / license | 추가 안 함 (이미 있음) |

> Private 저장소에서도 Pages를 쓸 수 있지만 유료 플랜이 필요합니다.
> **Public으로 만들면 소스코드가 전부 공개됩니다** — 1번의 비밀값 확인이 그래서 중요합니다.

### 3-2. 로컬에서 올리기

```bash
cd ~/name-compat           # 프로젝트 폴더

git init
git branch -M main
git add .
git status --short          # .env 없는지 마지막 확인!
git commit -m "韓国式 名前相性診断: EC2/Docker/RDS 구성 + 정적판"

git remote add origin https://github.com/<내_아이디>/name-compat.git
git push -u origin main
```

`<내_아이디>` 를 실제 GitHub 사용자명으로 바꿉니다.

**인증을 물어보면**: 비밀번호가 아니라 **Personal Access Token**이 필요합니다.
GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic) →
Generate new token → `repo` 권한 체크 → 생성된 토큰을 비밀번호 자리에 붙여넣기.

(또는 GitHub CLI 사용: `brew install gh` → `gh auth login` → 브라우저 로그인)

---

## 4. Pages 켜기

저장소 페이지 → **Settings** → 좌측 메뉴 **Pages**

| 항목 | 값 |
|---|---|
| Source | **Deploy from a branch** |
| Branch | `main` |
| Folder | **`/docs`** ← 중요 |

**Save** 클릭.

1~3분 뒤 상단에 주소가 나타납니다:

```
https://<내_아이디>.github.io/name-compat/
```

이 주소는 **누구나** 접속할 수 있습니다. 일본 동료에게 그냥 링크를 보내면 됩니다.

---

## 5. 수정하고 다시 올리기

```bash
# 프론트엔드 수정 후
python3 tools/build_static.py

git add .
git commit -m "수정 내용"
git push
```

push 후 1~2분이면 반영됩니다. 반영이 안 보이면 브라우저 강력 새로고침(⌘⇧R).

배포 진행 상황은 저장소의 **Actions** 탭에서 볼 수 있습니다.

---

## 6. EC2판과 함께 쓰는 법

두 개를 동시에 운영하는 게 실제로 편합니다.

| | 용도 |
|---|---|
| **GitHub Pages** | 동료에게 링크 공유. 회사 방화벽·SSH 터널 무관 |
| **EC2** | Datadog 관측 실습, 서버 운영 연습, 진짜 DB에 데이터 모으기 |

같은 알고리즘이라 **점수가 동일**합니다 (`야마다` = 93%). 그래서 "정적판에서 본 결과가 서버판에서도 같다"를 확인하는 것 자체가 좋은 검증이 됩니다.

---

## 7. 자주 나는 문제

| 증상 | 원인 / 조치 |
|---|---|
| 404 페이지 | Folder가 `/docs` 인지 확인. `docs/index.html` 이 push 되었는지 확인 |
| CSS가 깨져 보임 | 정적판은 CSS가 HTML에 인라인되어 있어 이 문제가 없음. 깨지면 `build_static.py` 재실행 |
| 랭킹이 사라짐 | 정상. localStorage는 브라우저별·시크릿모드에서 초기화됨 |
| 다른 사람 랭킹이 안 보임 | 정상. 서버가 없어서 공유되지 않음 |
| 수정이 반영 안 됨 | Actions 탭에서 배포 완료 확인 → 브라우저 강력 새로고침 |
| `.env` 를 올려버림 | **즉시 키 폐기 후 재발급.** 히스토리 삭제만으로는 부족 |

---

## 8. 더 하고 싶다면

| 하고 싶은 것 | 방법 |
|---|---|
| 랭킹을 모두가 공유 | 서버가 필요 → EC2판을 사내 승인된 경로로 공개, 또는 서버리스(Cloudflare Workers + D1 등) |
| 내 도메인 붙이기 | Pages 설정의 Custom domain + DNS CNAME |
| 접속자 수 보기 | GitHub Pages에는 없음 → Datadog RUM 또는 간단한 분석 도구 추가 |
| 자동 빌드 | GitHub Actions로 push 시 `build_static.py` 자동 실행 |
