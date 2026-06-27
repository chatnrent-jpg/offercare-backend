import re
import httpx

url = "https://health.maryland.gov/ohcq/Pages/OHCQ-Licensee-Directories.aspx"
r = httpx.get(url, timeout=30, follow_redirects=True)
print("status", r.status_code)
for m in re.findall(r'href="([^"]+)"', r.text):
    low = m.lower()
    if "xls" in low or "long" in low or "assisted" in low:
        print(m)
