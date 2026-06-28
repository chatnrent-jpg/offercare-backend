import requests

r = requests.get("http://127.0.0.1:8000/portal/", timeout=10)
print("X-Portal-Build:", r.headers.get("X-Portal-Build"))
print("isAuthError in app.js:", "isAuthError" in js.text)
print("open-shifts primary path:", 'api(`/api/shifts/open?${baseQuery}`)' in js.text)
print("API_TIMEOUT_MS:", "API_TIMEOUT_MS" in js.text)
print('id="app" in body:', 'id="app"' in r.text)
js = requests.get("http://127.0.0.1:8000/portal/app.js", timeout=10)
print("purgeStalePortalCache:", "purgeStalePortalCache" in js.text)
