"""
preview.html 을 만든다.

frontend/index.html + css + js + tools/mock-api.js 를 하나의 HTML로 인라인해서,
서버 없이 브라우저로 열어 UI를 확인할 수 있게 한다.

    python3 tools/build_preview.py
    open preview.html
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
css = (ROOT / "frontend" / "css" / "style.css").read_text(encoding="utf-8")
kana = (ROOT / "frontend" / "js" / "kana2hangul.js").read_text(encoding="utf-8")
app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
mock = (ROOT / "tools" / "mock-api.js").read_text(encoding="utf-8")

import re

html = re.sub(
    r'<link rel="stylesheet" href="/css/style\.css[^"]*">',
    lambda _: "<style>\n" + css + "\n</style>",
    html,
)

# mock-api 는 app.js 보다 먼저 로드해야 fetch를 가로챌 수 있다
html = re.sub(
    r'<script src="/js/kana2hangul\.js[^"]*"></script>\s*<script src="/js/app\.js[^"]*"></script>',
    lambda _: (
        "<script>\n" + mock + "\n</script>\n"
        "<script>\n" + kana + "\n</script>\n"
        "<script>\n" + app + "\n</script>"
    ),
    html,
)

banner = (
    '<p style="max-width:520px;margin:0 auto;padding:10px 16px;'
    'font-size:11px;color:#9a93a3;text-align:center">'
    'これはデザイン確認用のプレビューです（APIはブラウザ内モック / データは保存されません）'
    "</p>"
)
html = html.replace("<div class=\"wrap\">", banner + '\n<div class="wrap">')

out = ROOT / "preview.html"
out.write_text(html, encoding="utf-8")
print(f"wrote {out}  ({len(html):,} bytes)")
