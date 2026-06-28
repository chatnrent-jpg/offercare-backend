import requests

r = requests.get("http://127.0.0.1:8000/portal/", timeout=10)
print("X-Portal-Build:", r.headers.get("X-Portal-Build"))
print("portal-step11-2026 in body:", "portal-step11-2026" in r.text)
print('id="app" in body:', 'id="app"' in r.text)
js = requests.get("http://127.0.0.1:8000/portal/app.js", timeout=10)
print("purgeStalePortalCache:", "purgeStalePortalCache" in js.text)
