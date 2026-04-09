#!/usr/bin/env python3
"""Test curl_cffi to bypass CloudFront TLS fingerprinting."""
from curl_cffi import requests as cf_requests
import json, re

session = cf_requests.Session(impersonate="chrome124")

url = 'https://www.nawy.com/search?category=property&page_number=1'
print(f"Fetching: {url}")

resp = session.get(url)
print(f"Status: {resp.status_code}")

if resp.status_code == 200:
    pattern = r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>'
    match = re.search(pattern, resp.text, re.DOTALL)
    if match:
        data = json.loads(match.group(1))
        pp = data.get('props', {}).get('pageProps', {})
        ssr = pp.get('loadedSearchResultsSSR', {})
        print(f"Total units: {ssr.get('total')}")
        print(f"Results on page: {len(ssr.get('results', []))}")
        if ssr.get('results'):
            first = ssr['results'][0]
            print(f"First: {first.get('title')} (id={first.get('id')})")
    else:
        print("No __NEXT_DATA__ found")
else:
    print(f"Body: {resp.text[:300]}")
