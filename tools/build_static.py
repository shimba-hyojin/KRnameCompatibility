"""
GitHub Pages 용 정적판을 만든다.

frontend/ 의 HTML·CSS·JS 와 tools/static-api.js 를 하나의 index.html 로 합쳐서
docs/index.html 에 쓴다. GitHub Pages 의 "main 브랜치 /docs 폴더" 설정으로 바로 공개된다.

    python3 tools/build_static.py

서버(Flask/RDS)가 없는 환경이므로:
  * 궁합 계산은 브라우저에서 (알고리즘 동일 → 점수도 동일)
  * 랭킹은 localStorage 에 저장 (브라우저별로 각자 보관)
  * 포춘쿠키는 로컬 메시지
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
css = (ROOT / "frontend" / "css" / "style.css").read_text(encoding="utf-8")
kana = (ROOT / "frontend" / "js" / "kana2hangul.js").read_text(encoding="utf-8")
app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
static_api = (ROOT / "tools" / "static-api.js").read_text(encoding="utf-8")

# CSS 인라인
html = re.sub(
    r'<link rel="stylesheet" href="/css/style\.css[^"]*">',
    lambda _: "<style>\n" + css + "\n</style>",
    html,
)
# 주석으로 남은 캐시 안내는 정적판에서 불필요
html = html.replace("<!-- ?v= 는 캐시 무효화용. 프론트엔드를 고칠 때마다 숫자를 올린다. -->\n", "")

# RUM 은 그대로 인라인한다 (GitHub Pages 에서도 브라우저가 직접 Datadog へ送る).
# env 를 pages 로 上書きして EC2 版と区別できるようにする。
rum = (ROOT / "frontend" / "js" / "rum.js").read_text(encoding="utf-8")
rum = rum.replace("env: 'prod'", "env: 'pages'")
html = re.sub(
    r'<script src="/js/rum\.js[^"]*"></script>',
    lambda _: "<script>\n" + rum + "\n</script>",
    html,
)

# JS 인라인 — static-api 가 app.js 보다 먼저 와야 fetch 를 가로챈다
html = re.sub(
    r'<script src="/js/kana2hangul\.js[^"]*"></script>\s*<script src="/js/app\.js[^"]*"></script>',
    lambda _: (
        "<script>\n" + static_api + "\n</script>\n"
        "<script>\n" + kana + "\n</script>\n"
        "<script>\n" + app + "\n</script>"
    ),
    html,
)

# 정적판 안내 문구 + GitHub 링크 자리
note = (
    '<p class="foot__tech" style="margin-top:6px">'
    "このページはブラウザだけで動く簡易版です（記録はこの端末に保存されます）"
    "</p>"
)
html = html.replace(
    '<p class="foot__tech">Flask · MySQL(RDS) · Nginx · Docker · EC2 · Datadog</p>',
    '<p class="foot__tech">Flask · MySQL(RDS) · Nginx · Docker · EC2 · Datadog</p>\n    ' + note,
)

# SNS 공유용 메타 태그
og = """<meta property="og:type" content="website">
<meta property="og:title" content="韓国式 名前相性診断">
<meta property="og:description" content="ハングルの画数だけで相性を占います。カタカナからの変換つき。">
<meta name="twitter:card" content="summary">"""
html = html.replace("</head>", og + "\n</head>")

out_dir = ROOT / "docs"
out_dir.mkdir(exist_ok=True)
(out_dir / "index.html").write_text(html, encoding="utf-8")

# Jekyll 처리를 건너뛰게 한다 (밑줄로 시작하는 파일이 없어도 습관적으로 넣어둔다)
(out_dir / ".nojekyll").write_text("", encoding="utf-8")

print(f"wrote {out_dir / 'index.html'}  ({len(html):,} bytes)")
print(f"wrote {out_dir / '.nojekyll'}")
