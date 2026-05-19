"""
InsightX v6.0.0-alpha Release-notes PPT generator

執行：
    cd ppt && /path/to/.venv/bin/python generate_v6.py

產出：
    ppt/InsightX_v6.0.0-alpha.pptx

設計：
- 共用 ppt/generate.py 的色票 + 排版 helper 思路（直接內聯，因為 generate.py
  不是 module-shaped）
- 16:9 sandwich：dark cover/closing + light editorial content
- 配色（與 v4/v6 UI 一致）
- 14 張，磁石卡片風（左 §編號 + kicker，右大標 + 內文）
"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pathlib import Path

# ─── Palette ────────────────────────────────────────────
INK       = RGBColor(0x1a, 0x1f, 0x1c)
INK_2     = RGBColor(0x5b, 0x66, 0x61)
INK_3     = RGBColor(0x8a, 0x93, 0x8e)
INK_4     = RGBColor(0xb0, 0xb6, 0xb3)
RULE      = RGBColor(0xcd, 0xd1, 0xce)
PAPER     = RGBColor(0xfa, 0xf7, 0xf2)
PAPER_2   = RGBColor(0xf3, 0xee, 0xe5)
CORAL     = RGBColor(0xd6, 0x5a, 0x3a)
FOREST    = RGBColor(0x2c, 0x5f, 0x2d)
WHITE     = RGBColor(0xff, 0xff, 0xff)
BLACK     = RGBColor(0x0d, 0x0f, 0x0e)

SERIF = "Noto Serif TC"
SANS  = "Noto Sans TC"
MONO  = "Menlo"

WIDTH = 13.333
HEIGHT = 7.5

HERE = Path(__file__).resolve().parent
HERO_IMG = HERE.parent / "src" / "static" / "v2" / "assets" / "hero-listening.png"
V4_SCREENSHOTS = HERE.parent / "docs" / "screenshots" / "v4"


# ─── Helpers ───────────────────────────────────────────
def add_bg(slide, color):
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(WIDTH), Inches(HEIGHT))
    bg.fill.solid()
    bg.fill.fore_color.rgb = color
    bg.line.fill.background()


def add_text(slide, text, x, y, w, h, *, size=14, bold=False, color=INK, font=SANS,
             align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = valign
    tf.margin_left = Emu(0); tf.margin_right = Emu(0)
    tf.margin_top = Emu(0); tf.margin_bottom = Emu(0)
    p = tf.paragraphs[0]
    p.alignment = align
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.color.rgb = color
    r.font.name = font
    return tb


def add_kicker(slide, num, label, x=0.5, y=0.4):
    add_text(slide, f"§ {num}", x, y, 1, 0.3, size=11, color=CORAL, font=MONO)
    add_text(slide, label.upper(), x + 0.7, y, 6, 0.3, size=11, color=INK_3, font=MONO)


def add_title(slide, text, x=0.5, y=0.85, w=12, h=1.2, color=INK):
    add_text(slide, text, x, y, w, h, size=44, bold=True, color=color, font=SERIF)


def add_subtitle(slide, text, x=0.5, y=2.1, w=12, h=0.5, color=INK_2):
    add_text(slide, text, x, y, w, h, size=15, color=color, font=SANS)


def add_rule_line(slide, x, y, w, color=RULE):
    line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Emu(9525))
    line.fill.solid()
    line.fill.fore_color.rgb = color
    line.line.fill.background()


def add_image(slide, path, x, y, w, h):
    if not Path(path).exists():
        # Fallback: a paper-toned placeholder rect
        rect = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
        rect.fill.solid(); rect.fill.fore_color.rgb = PAPER_2
        rect.line.color.rgb = INK_4
        add_text(slide, f"(image missing: {Path(path).name})",
                 x, y + h/2 - 0.2, w, 0.4, size=11, color=INK_3, font=MONO, align=PP_ALIGN.CENTER)
        return
    slide.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w), Inches(h))


# ─── Build deck ─────────────────────────────────────────
prs = Presentation()
prs.slide_width = Inches(WIDTH)
prs.slide_height = Inches(HEIGHT)
blank = prs.slide_layouts[6]


# ╔══════════════════════════════════════════════════════════════╗
# ║ Slide 1: Cover                                                ║
# ╚══════════════════════════════════════════════════════════════╝
s = prs.slides.add_slide(blank)
add_bg(s, BLACK)
dot = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.5), Inches(0.5), Inches(0.45), Inches(0.45))
dot.fill.solid(); dot.fill.fore_color.rgb = CORAL; dot.line.fill.background()
add_text(s, "i", 0.5, 0.43, 0.45, 0.45, size=22, bold=True, color=WHITE,
         font=SERIF, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
add_text(s, "insightx", 1.05, 0.5, 3, 0.5, size=20, bold=True, color=WHITE, font=SERIF)
add_text(s, "V 6 . 0 . 0 - A L P H A   ·   L I V E", 9.5, 0.55, 3.5, 0.3,
         size=10, color=INK_3, font=MONO, align=PP_ALIGN.RIGHT)

add_text(s, "RELEASE NOTES · 2026-05-19", 0.7, 2.5, 8, 0.3,
         size=11, color=CORAL, font=MONO)
add_text(s, "從 async 到 sync，", 0.7, 3.0, 12, 1.4, size=72, bold=True, color=WHITE, font=SERIF)
add_text(s, "從本地到雲端。", 0.7, 4.4, 12, 1.4, size=72, bold=True, color=WHITE, font=SERIF)
add_text(s, "v5 → v6 — 工作區持久化、Turso 雲端 DB、HF Spaces 部署、Codex img2 雜誌封面",
         0.7, 6.0, 12, 0.5, size=15, color=INK_4, font=SANS)
add_rule_line(s, 0.7, 6.8, 11.9, color=RGBColor(0x44, 0x4d, 0x49))
add_text(s, "INSIGHTX  ·  v6.0.0-ALPHA  ·  MIT", 0.7, 6.95, 12, 0.3,
         size=10, color=INK_4, font=MONO)
add_text(s, "Jordan711-insightx-demo.hf.space", 8, 6.95, 5, 0.3,
         size=10, color=INK_4, font=MONO, align=PP_ALIGN.RIGHT)


# ╔══════════════════════════════════════════════════════════════╗
# ║ Slide 2: The journey                                          ║
# ╚══════════════════════════════════════════════════════════════╝
s = prs.slides.add_slide(blank)
add_bg(s, PAPER)
add_kicker(s, "01", "the journey")
add_title(s, "四個版本，半年。")
add_subtitle(s, "從一次性的店家分析 demo，到雲端部署的持久工作區。")

versions = [
    ("v3", "2026-04", "Google Maps + YouTube 雙模式", INK_3),
    ("v4", "2026-04", "single-file React + magazine UI", INK_2),
    ("v5", "2026-05", "持久工作區 + 9-table schema", FOREST),
    ("v6", "2026-05", "Turso + HF Spaces + sync 重寫", CORAL),
]
for i, (ver, when, what, color) in enumerate(versions):
    y = 3.5 + i * 0.65
    # dot
    d = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.7), Inches(y + 0.15), Inches(0.18), Inches(0.18))
    d.fill.solid(); d.fill.fore_color.rgb = color; d.line.fill.background()
    add_text(s, ver, 1.1, y, 0.8, 0.4, size=20, bold=True, color=color, font=SERIF)
    add_text(s, when, 2.1, y + 0.05, 1.5, 0.35, size=10, color=INK_3, font=MONO)
    add_text(s, what, 3.6, y, 9, 0.4, size=15, color=INK, font=SANS)

# subtle vertical line connecting dots
line = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.78), Inches(3.7), Emu(9525), Inches(2.0))
line.fill.solid(); line.fill.fore_color.rgb = INK_4; line.line.fill.background()


# ╔══════════════════════════════════════════════════════════════╗
# ║ Slide 3: v5 — persistent workspace                            ║
# ╚══════════════════════════════════════════════════════════════╝
s = prs.slides.add_slide(blank)
add_bg(s, PAPER)
add_kicker(s, "02", "v5 — workspace")
add_title(s, "從一次性分析，變成你的店家檔案。")
add_subtitle(s, "v5 加了 9-table schema、cascade-delete、SSE job streaming。")

bullets = [
    ("9 張資料表", "User · Workspace · Store · ReviewSource · ScrapeJob · Review · AnalysisRun · GeneratedAsset · Report"),
    ("Async SQLAlchemy 2.0", "FastAPI + asyncpg / aiosqlite，全 ORM"),
    ("Cascade 刪除完整性", "DELETE /stores 連帶清掉 sources / jobs / reviews / runs / reports"),
    ("3 輪 Codex peer review", "Round 3 加上 passive_deletes + _safe_commit_or_log race-window 保護"),
]
for i, (title, body) in enumerate(bullets):
    y = 3.3 + i * 0.95
    # bullet bar
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.7), Inches(y + 0.05), Inches(0.05), Inches(0.65))
    bar.fill.solid(); bar.fill.fore_color.rgb = FOREST; bar.line.fill.background()
    add_text(s, title, 0.95, y, 4, 0.4, size=18, bold=True, color=INK, font=SERIF)
    add_text(s, body, 0.95, y + 0.4, 11.5, 0.5, size=13, color=INK_2, font=SANS)


# ╔══════════════════════════════════════════════════════════════╗
# ║ Slide 4: Why sync? (the Turso pivot)                          ║
# ╚══════════════════════════════════════════════════════════════╝
s = prs.slides.add_slide(blank)
add_bg(s, PAPER)
add_kicker(s, "03", "the turso pivot")
add_title(s, "為什麼 v6 把整個 stack 改 sync？")
add_subtitle(s, "因為 Turso 的 Python driver 只支援 sync — async 路根本走不通。")

# Two boxes side by side
def stack_box(x, y, w, h, header, header_color, lines, base_color):
    rect = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    rect.fill.solid(); rect.fill.fore_color.rgb = base_color
    rect.line.color.rgb = INK
    add_text(s, header, x + 0.2, y + 0.15, w - 0.4, 0.4, size=14, bold=True, color=header_color, font=MONO)
    for i, ln in enumerate(lines):
        add_text(s, ln, x + 0.2, y + 0.7 + i * 0.4, w - 0.4, 0.4, size=12, color=INK, font=SANS)

stack_box(0.7, 3.0, 5.5, 3.5, "v5 ASYNC ✗", CORAL, [
    "FastAPI 0.109 + async routes",
    "SQLAlchemy 2.0 + asyncpg / aiosqlite",
    "asyncio.create_task() bg workers",
    "asyncio.Queue + Event",
    "─",
    "create_async_engine('sqlite+libsql://...')",
    "→ InvalidRequestError",
    "sqlalchemy-libsql 0.2 不支援 async",
], PAPER_2)

stack_box(7.1, 3.0, 5.5, 3.5, "v6 SYNC ✓", FOREST, [
    "FastAPI 0.109 + sync routes (threadpool)",
    "SQLAlchemy 2.0 + sqlalchemy-libsql",
    "threading.Thread(daemon=True) workers",
    "queue.Queue + threading.Event",
    "─",
    "create_engine('sqlite+libsql://...')",
    "→ works",
    "Turso libsql 完全可用",
], PAPER_2)

add_text(s, "Turso 是 SQLite-compatible 的 serverless DB；libsql 是它的 Rust 實作，",
         0.7, 6.7, 12, 0.3, size=11, color=INK_3, font=SANS)
add_text(s, "Python binding 還沒做 async wrapper — sync 是唯一路。",
         0.7, 7.0, 12, 0.3, size=11, color=INK_3, font=SANS)


# ╔══════════════════════════════════════════════════════════════╗
# ║ Slide 5: v6 stack diagram                                     ║
# ╚══════════════════════════════════════════════════════════════╝
s = prs.slides.add_slide(blank)
add_bg(s, PAPER)
add_kicker(s, "04", "v6 stack")
add_title(s, "整條鏈，全部 sync。")
add_subtitle(s, "Web 層、ORM、background worker、alembic migration — 都不再有 async/await。")

# Stack layers (top to bottom)
layers = [
    ("FRONTEND", "Babel-standalone React · single-file SPA", CORAL, PAPER_2),
    ("WEB", "FastAPI sync routes · uvicorn threadpool", INK, PAPER_2),
    ("LLM", "google-genai · MODEL_CHAIN multi-fallback · per-call timeout", CORAL, PAPER_2),
    ("JOBS", "threading.Thread daemons · queue.Queue · threading.Semaphore", INK, PAPER_2),
    ("ORM", "SQLAlchemy 2.0 sync · sqlalchemy-libsql + libsql-experimental", CORAL, PAPER_2),
    ("DB", "Turso (libsql, serverless SQLite) · ~30ms 日本機房 latency", FOREST, PAPER_2),
]
for i, (label, desc, label_color, bg_color) in enumerate(layers):
    y = 3.0 + i * 0.6
    rect = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.7), Inches(y), Inches(11.9), Inches(0.55))
    rect.fill.solid(); rect.fill.fore_color.rgb = bg_color
    rect.line.color.rgb = INK
    add_text(s, label, 0.9, y + 0.1, 2, 0.4, size=12, bold=True, color=label_color, font=MONO)
    add_text(s, desc, 3.0, y + 0.1, 9.5, 0.4, size=12, color=INK, font=SANS)


# ╔══════════════════════════════════════════════════════════════╗
# ║ Slide 6: v6 hero illustration                                 ║
# ╚══════════════════════════════════════════════════════════════╝
s = prs.slides.add_slide(blank)
add_bg(s, PAPER)
add_kicker(s, "05", "v6 — hero illustration")
add_title(s, "Codex img2 重新繪製 hero。")
add_subtitle(s, "Saul Bass × 新雜誌 × risograph — 不是程式畫的，是 AI 算的編輯級插圖。")

# Hero image on left
add_image(s, HERO_IMG, 0.7, 2.7, 4.5, 4.5)

# Description on right
add_text(s, "概念：universal listening post", 5.7, 3.0, 7, 0.5, size=18, bold=True, color=INK, font=SERIF)
add_text(s, "中央 sonar 接收器 + 周圍 7 個 source emitter：",
         5.7, 3.7, 7, 0.4, size=13, color=INK_2, font=SANS)
emitters = [
    "⭐ Google Maps 星等 pin",
    "🎙 麥克風 + 聲波（廣義 audio）",
    "▶ YouTube play + comment stack",
    "💬 chat bubble",
    "❤ heart + comment count (IG-like)",
    "☰ scroll/list (Threads/TikTok-like)",
    "✉ quote envelope（任何書面意見）",
]
for i, em in enumerate(emitters):
    add_text(s, em, 5.7, 4.2 + i * 0.35, 7, 0.3, size=12, color=INK_2, font=SANS)
add_text(s, "Dotted arrows 從各 source 指向中心 — 多源匯流。負空間留給未來 platform。",
         5.7, 6.85, 7, 0.4, size=11, color=INK_3, font=SANS)


# ╔══════════════════════════════════════════════════════════════╗
# ║ Slide 7: LLM resilience — multi-model fallback chain          ║
# ╚══════════════════════════════════════════════════════════════╝
s = prs.slides.add_slide(blank)
add_bg(s, PAPER)
add_kicker(s, "06", "v6 — llm resilience")
add_title(s, "Gemini 掛了，使用者不該知道。")
add_subtitle(s, "MODEL_CHAIN 自動切換 — 5xx / 429 / transport 錯誤都會 fall through 到下一個 model。")

# 4 models in horizontal flow
models = [
    ("gemma-4-26b-a4b-it", "MoE Active 4B\n推論快", CORAL, "PRIMARY"),
    ("gemma-4-31b-it", "Dense 31B\nthinking on", INK, "FALLBACK 1"),
    ("gemini-2.5-flash", "Google GA\n高 quota", INK, "FALLBACK 2"),
    ("gemini-2.5-flash-lite", "輕量備援\n最後保險", INK_3, "FALLBACK 3"),
]
for i, (name, desc, color, role) in enumerate(models):
    x = 0.5 + i * 3.15
    rect = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(3.3), Inches(3.0), Inches(2.5))
    rect.fill.solid(); rect.fill.fore_color.rgb = PAPER_2
    rect.line.color.rgb = color
    add_text(s, role, x + 0.15, 3.45, 2.7, 0.3, size=10, color=color, font=MONO)
    add_text(s, name, x + 0.15, 3.85, 2.7, 0.5, size=14, bold=True, color=INK, font=MONO)
    add_text(s, desc, x + 0.15, 4.5, 2.7, 1.1, size=12, color=INK_2, font=SANS)
    # arrow
    if i < 3:
        add_text(s, "→", x + 3.0, 4.3, 0.2, 0.5, size=20, color=INK_3, font=SANS, align=PP_ALIGN.CENTER)

add_text(s, "ClientError 4xx 非 429（我們的 bug）→ 立即 raise，不浪費時間試其他 model",
         0.7, 6.2, 12, 0.4, size=12, color=INK_3, font=SANS)
add_text(s, "ServerError 5xx / RESOURCE_EXHAUSTED / NetworkError → 下一個 model",
         0.7, 6.6, 12, 0.4, size=12, color=INK_3, font=SANS)
add_text(s, "Per-call http_options.timeout 用剩餘 budget 算 → 單次 attempt 不會超過總 budget",
         0.7, 7.0, 12, 0.4, size=12, color=INK_3, font=SANS)


# ╔══════════════════════════════════════════════════════════════╗
# ║ Slide 8: HF Spaces deploy                                     ║
# ╚══════════════════════════════════════════════════════════════╝
s = prs.slides.add_slide(blank)
add_bg(s, PAPER)
add_kicker(s, "07", "v6 — deploy")
add_title(s, "$0/月跑在 Hugging Face Spaces。")
add_subtitle(s, "單階段 Docker、Turso libsql、Codex 3 輪 deploy review APPROVE。")

# Left: deploy steps
add_text(s, "5 個步驟", 0.7, 3.0, 5, 0.5, size=18, bold=True, color=INK, font=SERIF)
steps = [
    ("1.", "turso db create insightx-demo --location nrt"),
    ("2.", "huggingface.co/new-space → Docker SDK"),
    ("3.", "設 5 個 Space secrets"),
    ("4.", "git clone Space repo → cp 原始碼 → git push"),
    ("5.", "等 build (~3min) → 上線"),
]
for i, (num, txt) in enumerate(steps):
    y = 3.7 + i * 0.6
    add_text(s, num, 0.7, y, 0.4, 0.5, size=14, bold=True, color=CORAL, font=MONO)
    add_text(s, txt, 1.1, y, 5.5, 0.5, size=12, color=INK, font=MONO)

# Right: stack
add_text(s, "Dockerfile 重點", 7.5, 3.0, 5, 0.5, size=18, bold=True, color=INK, font=SERIF)
highlights = [
    "FROM python:3.10-slim · 單階段",
    "port 7860（HF default）",
    "non-root uid=1000 user",
    "alembic upgrade head 開機時跑",
    "HEALTHCHECK /api/meta",
    "JSON-form CMD + exec → uvicorn IS PID 1",
    "image size 408 MB（移掉 build-essential 後）",
]
for i, h in enumerate(highlights):
    add_text(s, "·  " + h, 7.5, 3.7 + i * 0.45, 5.5, 0.4, size=12, color=INK_2, font=SANS)


# ╔══════════════════════════════════════════════════════════════╗
# ║ Slide 9: v4 → v5 workspace bridge                             ║
# ╚══════════════════════════════════════════════════════════════╝
s = prs.slides.add_slide(blank)
add_bg(s, PAPER)
add_kicker(s, "08", "v6 — bridge")
add_title(s, "Landing 分析 → 工作區持久化。")
add_subtitle(s, "v4 stateless + v5 持久 schema 之間的橋，default OFF（多租戶安全）。")

# Flow diagram
add_text(s, "Before v6 →", 0.7, 3.2, 2, 0.5, size=14, color=INK_3, font=MONO)
add_text(s, "v4 /api/analyze · 一次性 ·  ✗ 不寫 DB", 2.7, 3.2, 10, 0.5, size=14, color=INK, font=SANS)
add_text(s, "→ /workspace/ 永遠空空的", 2.7, 3.6, 10, 0.5, size=12, color=INK_3, font=SANS)

add_rule_line(s, 0.7, 4.3, 11.9)

add_text(s, "v6 fix →", 0.7, 4.7, 2, 0.5, size=14, color=CORAL, font=MONO)
add_text(s, "_persist_v4_analyze_to_workspace() bridge", 2.7, 4.7, 10, 0.5, size=14, color=INK, font=SANS)
bullets = [
    "✓ 寫入 Store · ReviewSource · ScrapeJob · Review · AnalysisRun",
    "✓ Dedupe by ReviewSource.external_url（同 URL 重分析 = 更新）",
    "✓ 非 fatal（失敗 log + 吞，user 看到的 API 回應不受影響）",
    "✓ Gate: IX_ENABLE_V4_WORKSPACE_PERSIST=1 才開",
]
for i, b in enumerate(bullets):
    add_text(s, b, 2.7, 5.15 + i * 0.4, 10, 0.4, size=12, color=INK_2, font=SANS)

add_text(s, "⚠️ 為什麼 default OFF：v5α 用 hardcoded default user，公開 demo 開了會讓 visitor 互看資料。",
         0.7, 6.9, 12, 0.3, size=11, color=CORAL, font=SANS)
add_text(s, "Cookie-based session scoping 在 v6.1 路線上。",
         0.7, 7.2, 12, 0.3, size=11, color=INK_3, font=SANS)


# ╔══════════════════════════════════════════════════════════════╗
# ║ Slide 10: Codex peer review                                   ║
# ╚══════════════════════════════════════════════════════════════╝
s = prs.slides.add_slide(blank)
add_bg(s, PAPER)
add_kicker(s, "09", "consensus")
add_title(s, "8 輪 Codex peer review，全部 APPROVE。")
add_subtitle(s, "雙 AI 共識才打 v6.0.0-alpha tag。")

reviews = [
    ("Phase 1: Sync refactor", [
        ("R1", "BLOCK", "per-call LLM timeout, queue cleanup, SSE worker cancel"),
        ("R2", "NEEDS-WORK", "needed producer-pop + idle reset"),
        ("R3", "APPROVE", "consensus"),
    ], CORAL),
    ("Phase 2: HF Spaces deploy", [
        ("R1", "NEEDS-FIXES", "report regen, build-essential, HEALTHCHECK"),
        ("R2", "WITH-NOTES", "initial recipe missing .dockerignore"),
        ("R3", "APPROVE", "clean"),
    ], FOREST),
    ("Phase 3: Pre-freeze full project", [
        ("R1", "BLOCK", "multi-tenant privacy via bridge"),
        ("R2", "APPROVE", "env-gate + deferred items doc'd"),
    ], INK),
]

y_offset = 3.0
for phase_name, rounds, color in reviews:
    add_text(s, phase_name, 0.7, y_offset, 6, 0.4, size=14, bold=True, color=color, font=SERIF)
    for j, (rnd, verdict, note) in enumerate(rounds):
        y = y_offset + 0.4 + j * 0.35
        add_text(s, rnd, 0.9, y, 0.6, 0.3, size=11, bold=True, color=color, font=MONO)
        add_text(s, verdict, 1.5, y, 1.5, 0.3, size=10, color=INK, font=MONO)
        add_text(s, note, 3.2, y, 9, 0.3, size=10, color=INK_3, font=SANS)
    y_offset += 0.4 + len(rounds) * 0.35 + 0.1


# ╔══════════════════════════════════════════════════════════════╗
# ║ Slide 11: Live demo screenshot                                ║
# ╚══════════════════════════════════════════════════════════════╝
s = prs.slides.add_slide(blank)
add_bg(s, PAPER)
add_kicker(s, "10", "live demo")
add_title(s, "現在就試。")
add_subtitle(s, "Jordan711-insightx-demo.hf.space — 不用註冊、不用安裝、月費 $0。")

# Landing screenshot
add_image(s, V4_SCREENSHOTS / "01-landing.png", 0.7, 2.9, 8.5, 4.5)

# URL callout box
url_box_x = 9.6
url_box_y = 3.0
rect = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(url_box_x), Inches(url_box_y), Inches(3.2), Inches(2.0))
rect.fill.solid(); rect.fill.fore_color.rgb = INK
rect.line.fill.background()
add_text(s, "DEMO URL", url_box_x + 0.2, url_box_y + 0.15, 3, 0.3, size=10, color=CORAL, font=MONO)
add_text(s, "Jordan711-", url_box_x + 0.2, url_box_y + 0.55, 3, 0.4, size=14, bold=True, color=WHITE, font=MONO)
add_text(s, "insightx-demo", url_box_x + 0.2, url_box_y + 0.9, 3, 0.4, size=14, bold=True, color=WHITE, font=MONO)
add_text(s, ".hf.space", url_box_x + 0.2, url_box_y + 1.25, 3, 0.4, size=14, bold=True, color=WHITE, font=MONO)
add_text(s, "貼 Google Maps URL", url_box_x + 0.2, url_box_y + 1.7, 3, 0.3, size=10, color=INK_4, font=MONO)

# Stack pill
add_text(s, "STACK", 9.7, 5.5, 1.5, 0.3, size=10, color=CORAL, font=MONO)
stack_items = ["HF Spaces Free", "Turso libsql", "Gemini × 4 models", "FastAPI sync"]
for i, it in enumerate(stack_items):
    add_text(s, "·  " + it, 9.7, 5.85 + i * 0.3, 4, 0.3, size=11, color=INK_2, font=SANS)


# ╔══════════════════════════════════════════════════════════════╗
# ║ Slide 12: Architecture diagram                                ║
# ╚══════════════════════════════════════════════════════════════╝
s = prs.slides.add_slide(blank)
add_bg(s, PAPER)
add_kicker(s, "11", "architecture")
add_title(s, "整個系統，一張圖。")
add_subtitle(s, "HF Spaces Docker container 接 Turso DB · Gemini API · Serper + YouTube Data API。")

# Outer box: HF container
container_x, container_y, container_w, container_h = 0.7, 3.0, 7.5, 4.0
rect = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(container_x), Inches(container_y), Inches(container_w), Inches(container_h))
rect.fill.solid(); rect.fill.fore_color.rgb = PAPER_2
rect.line.color.rgb = INK
add_text(s, "HF SPACES (DOCKER, port 7860)", container_x + 0.2, container_y + 0.15, 5, 0.3, size=10, color=INK_3, font=MONO)

# Inner: FastAPI
fast_x, fast_y = container_x + 0.5, container_y + 0.7
fast_w, fast_h = 6.5, 1.0
rect = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(fast_x), Inches(fast_y), Inches(fast_w), Inches(fast_h))
rect.fill.solid(); rect.fill.fore_color.rgb = WHITE; rect.line.color.rgb = INK
add_text(s, "FastAPI sync", fast_x + 0.2, fast_y + 0.1, 4, 0.3, size=12, bold=True, color=INK, font=MONO)
add_text(s, "/api/* (v4 stateless)   ·   /api/v5/* (persistent)   ·   /workspace/", fast_x + 0.2, fast_y + 0.5, 6, 0.3, size=10, color=INK_3, font=MONO)

# Inner: services row
svc_y = container_y + 2.0
services = [("LLMService", "MODEL_CHAIN"), ("SessionLocal", "sync ORM"), ("Threads", "bg workers")]
for i, (n, sub) in enumerate(services):
    x = container_x + 0.5 + i * 2.25
    rect = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(svc_y), Inches(2.0), Inches(0.9))
    rect.fill.solid(); rect.fill.fore_color.rgb = WHITE; rect.line.color.rgb = INK
    add_text(s, n, x + 0.15, svc_y + 0.1, 1.8, 0.3, size=11, bold=True, color=INK, font=MONO)
    add_text(s, sub, x + 0.15, svc_y + 0.5, 1.8, 0.3, size=9, color=INK_3, font=MONO)

# Inner: scraper
scr_y = container_y + 3.2
rect = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(fast_x), Inches(scr_y), Inches(fast_w), Inches(0.6))
rect.fill.solid(); rect.fill.fore_color.rgb = WHITE; rect.line.color.rgb = INK
add_text(s, "ScraperService (Serper + YouTube Data v3 + library fallback)", fast_x + 0.2, scr_y + 0.15, 6, 0.3, size=11, color=INK, font=MONO)

# External services on right
ext_x = 9.0
externals = [
    ("Turso", "libsql, nrt region\n5GB free", FOREST),
    ("Gemini API", "4-model chain\nfree tier", CORAL),
    ("Serper", "Google Maps\nreviews", INK),
    ("YouTube API", "Data v3\n10k units/day", INK),
]
for i, (name, desc, color) in enumerate(externals):
    y = container_y + i * 1.05
    rect = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(ext_x), Inches(y), Inches(3.5), Inches(0.9))
    rect.fill.solid(); rect.fill.fore_color.rgb = PAPER_2
    rect.line.color.rgb = color
    add_text(s, name, ext_x + 0.2, y + 0.1, 3.2, 0.3, size=12, bold=True, color=color, font=MONO)
    add_text(s, desc, ext_x + 0.2, y + 0.45, 3.2, 0.4, size=10, color=INK_2, font=SANS)


# ╔══════════════════════════════════════════════════════════════╗
# ║ Slide 13: v6.1 roadmap                                        ║
# ╚══════════════════════════════════════════════════════════════╝
s = prs.slides.add_slide(blank)
add_bg(s, PAPER)
add_kicker(s, "12", "v6.1 roadmap")
add_title(s, "已知限制，5 條全交給 v6.1。")
add_subtitle(s, "Codex 在 pre-freeze review 找到的；alpha 階段可接受，正式版必修。")

items = [
    ("1.", "Cookie-based session scoping", "目前 hardcoded default user；v6.1 用 HttpOnly cookie + per-visitor anonymous user"),
    ("2.", "v5 by-id endpoints 加 ownership scoping", "_get_owned_store(session, store_id) helper + 12+ 端點 audit"),
    ("3.", "Store UniqueConstraint(workspace_id, primary_url)", "alembic migration + IntegrityError retry → 防 concurrent dup"),
    ("4.", "Review dedupe via external_id", "sha256(source_id|author|date|text)[:32]，配合既有的 UniqueConstraint"),
    ("5.", "AnalysisRun.model_id 記真實 post-fallback model", "_generate() 改回 (text, model_used) tuple"),
]
for i, (num, title, desc) in enumerate(items):
    y = 3.0 + i * 0.85
    add_text(s, num, 0.7, y, 0.5, 0.4, size=20, bold=True, color=CORAL, font=SERIF)
    add_text(s, title, 1.3, y, 11, 0.4, size=15, bold=True, color=INK, font=SERIF)
    add_text(s, desc, 1.3, y + 0.4, 11, 0.4, size=12, color=INK_2, font=SANS)


# ╔══════════════════════════════════════════════════════════════╗
# ║ Slide 14: Closing                                             ║
# ╚══════════════════════════════════════════════════════════════╝
s = prs.slides.add_slide(blank)
add_bg(s, BLACK)
dot = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.5), Inches(0.5), Inches(0.45), Inches(0.45))
dot.fill.solid(); dot.fill.fore_color.rgb = CORAL; dot.line.fill.background()
add_text(s, "i", 0.5, 0.43, 0.45, 0.45, size=22, bold=True, color=WHITE,
         font=SERIF, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
add_text(s, "insightx", 1.05, 0.5, 3, 0.5, size=20, bold=True, color=WHITE, font=SERIF)

add_text(s, "FROZEN · 2026-05-19", 0.7, 2.5, 8, 0.3,
         size=11, color=CORAL, font=MONO)
add_text(s, "v6.0.0-alpha", 0.7, 3.0, 12, 1.4, size=72, bold=True, color=WHITE, font=SERIF)
add_text(s, "is live.", 0.7, 4.4, 12, 1.4, size=72, bold=True, color=WHITE, font=SERIF)

add_text(s, "Try it: https://Jordan711-insightx-demo.hf.space", 0.7, 6.0, 12, 0.5, size=15, color=INK_4, font=MONO)
add_text(s, "Source: github.com/GKS711/InsightX", 0.7, 6.4, 12, 0.5, size=13, color=INK_4, font=MONO)
add_text(s, "Tag: v6.0.0-alpha · Branch: claude/v6-sync-refactor", 0.7, 6.7, 12, 0.5, size=13, color=INK_4, font=MONO)

add_rule_line(s, 0.7, 7.1, 11.9, color=RGBColor(0x44, 0x4d, 0x49))
add_text(s, "BUILT WITH Codex peer review · auto-debug skill · 雙 AI 共識", 0.7, 7.25, 12, 0.3,
         size=10, color=INK_4, font=MONO)


# ─── Save ────────────────────────────────────────────
out_path = HERE / "InsightX_v6.0.0-alpha.pptx"
prs.save(str(out_path))
print(f"Saved: {out_path}")
print(f"Slides: {len(prs.slides)}")
print(f"File size: {out_path.stat().st_size:,} bytes")
