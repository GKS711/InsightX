import requests

url = "https://maps.app.goo.gl/aVaKSfbFpmom5Hoy7"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

try:
    print(f"Fetching {url}...")
    resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
    print(f"Status: {resp.status_code}")
    print(f"Final URL: {resp.url}")
    print("Content preview:")
    print(resp.text[:500])
except Exception as e:
    print(f"Request failed: {e}")
