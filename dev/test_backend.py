"""
InsightX — 後端診斷工具
用法：python dev/test_backend.py

逐一測試：
  [1] .env 設定
  [2] Serper API 連線
  [3] Gemini AI 連線
"""
import asyncio, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv()

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
SERPER_KEY = os.getenv("SERPER_API_KEY", "")

ok   = lambda m: print(f"  ✅ {m}")
fail = lambda m: print(f"  ❌ {m}")


def test_env():
    print("\n[1] 檢查 .env")
    ok(f"GEMINI_API_KEY ({GEMINI_KEY[:8]}...)") if GEMINI_KEY else fail("GEMINI_API_KEY 未設定")
    ok(f"SERPER_API_KEY ({SERPER_KEY[:8]}...)") if SERPER_KEY else fail("SERPER_API_KEY 未設定")


def test_serper():
    print("\n[2] 測試 Serper API")
    if not SERPER_KEY:
        fail("跳過（未設定 Key）"); return

    import urllib.request
    data = json.dumps({"q": "全家便利商店", "gl": "tw", "hl": "zh-tw"}).encode()
    req = urllib.request.Request(
        "https://google.serper.dev/maps",
        data=data,
        headers={"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
        places = result.get("places", [])
        ok(f"/maps 回傳 {len(places)} 個地點")
        if places:
            p = places[0]
            ok(f"  {p.get('title')} ★{p.get('rating')}（{p.get('ratingCount')} 則）")
    except Exception as e:
        fail(f"Serper 連線失敗：{e}")


async def test_gemini():
    print("\n[3] 測試 Gemini AI")
    if not GEMINI_KEY:
        fail("跳過（未設定 Key）"); return

    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_KEY)
        resp = await client.aio.models.generate_content(
            model="gemma-4-31b-it",
            contents="回覆 OK 即可",
        )
        ok(f"Gemini 回應：{resp.text[:50]}")
    except Exception as e:
        fail(f"Gemini 連線失敗：{e}")


async def main():
    print("=" * 45)
    print(" InsightX 後端診斷")
    print("=" * 45)
    test_env()
    test_serper()
    await test_gemini()
    print("\n" + "=" * 45)
    if GEMINI_KEY and SERPER_KEY:
        print("✅ 所有 API 正常，可以啟動 InsightX")
    else:
        print("⚠️ 請填入缺少的 API Key 後重新測試")
    print("=" * 45)


if __name__ == "__main__":
    asyncio.run(main())
