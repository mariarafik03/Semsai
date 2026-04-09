#!/usr/bin/env python3
"""Fix remaining compounds with null lng from compound detail pages."""
import sys, json, re, time, random
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from curl_cffi import requests
from database.connection import db_client
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn

console = Console(force_terminal=True)
session = requests.Session(impersonate="chrome124")
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
]

db_client.connect()
col = db_client._db['compounds']

# Find compounds with missing lng
broken = list(col.find(
    {'$or': [{'lng': None}, {'lng': {'$exists': False}}]},
    {'_id': 1, 'slug': 1, 'name': 1}
))

console.print(f"[cyan]Found {len(broken)} compounds with missing lng[/]")

fixed = 0
with Progress(
    SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
    BarColumn(), TextColumn("{task.percentage:>3.0f}%"),
    TextColumn("({task.completed}/{task.total})"),
    TimeElapsedColumn(), console=console
) as progress:
    task = progress.add_task("Fixing...", total=len(broken))
    for c in broken:
        slug = c.get('slug', '')
        if slug:
            url = f"https://www.nawy.com/compound/{slug}"
            try:
                time.sleep(random.uniform(1.0, 2.0))
                headers = {'User-Agent': random.choice(USER_AGENTS)}
                resp = session.get(url, headers=headers, timeout=25)
                if resp.status_code == 200:
                    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text, re.DOTALL)
                    if m:
                        data = json.loads(m.group(1))
                        comp = data.get('props', {}).get('pageProps', {}).get('compound', {})
                        if comp:
                            lat = comp.get('lat')
                            lng = comp.get('long')
                            if lat is not None and lng is not None:
                                col.update_one({'_id': c['_id']}, {'$set': {'lat': lat, 'lng': lng}})
                                fixed += 1
            except Exception:
                pass
        progress.update(task, advance=1,
                       description=f"Fixing... ({fixed} done)")

console.print(f"\n[green]Fixed {fixed} compounds[/]")
db_client.disconnect()
