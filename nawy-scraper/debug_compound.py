#!/usr/bin/env python3
"""Debug compound page structure - full keys."""
from curl_cffi import requests
import json, re

session = requests.Session(impersonate="chrome124")
url = "https://www.nawy.com/compound/1771-jirian-nations-of-sky"
resp = session.get(url, timeout=25)
if resp.status_code == 200:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text, re.DOTALL)
    if m:
        data = json.loads(m.group(1))
        comp = data['props']['pageProps']['compound']
        print("ALL compound keys:")
        for k in sorted(comp.keys()):
            v = comp[k]
            if isinstance(v, list):
                print(f"  {k}: list[{len(v)}]")
                if v and isinstance(v[0], dict):
                    print(f"    first keys: {list(v[0].keys())[:8]}")
            elif isinstance(v, dict):
                print(f"  {k}: dict keys={list(v.keys())[:8]}")
            else:
                print(f"  {k}: {repr(v)[:80]}")
