#!/usr/bin/env python3
"""Enrich compounds with data from their detail pages."""
import sys, json, re, time, random
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from curl_cffi import requests
from database.connection import db_client
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn

console = Console(force_terminal=True)

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
]

session = requests.Session(impersonate="chrome124")

def strip_html(text):
    if not text:
        return text
    text = re.sub(r'<[^>]+>', ' ', str(text))
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def fetch_compound_details(url):
    """Fetch compound page and extract enrichment data."""
    try:
        time.sleep(random.uniform(1.0, 2.0))
        headers = {'User-Agent': random.choice(USER_AGENTS)}
        resp = session.get(url, headers=headers, timeout=25)
        if resp.status_code != 200:
            return None
        
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text, re.DOTALL)
        if not m:
            return None
        
        data = json.loads(m.group(1))
        pp = data.get('props', {}).get('pageProps', {})
        comp = pp.get('compound', {})
        
        if not comp:
            return None
        
        result = {}
        
        # Description (strip HTML)
        desc = comp.get('description', '')
        if desc:
            result['description'] = strip_html(desc)
        
        # Amenities
        amenities = comp.get('amenities', [])
        if amenities:
            result['amenities'] = [a.get('name', '').strip() for a in amenities if a.get('name')]
        
        # Images (gallery)
        images = comp.get('images', [])
        if images:
            if isinstance(images[0], str):
                result['images_urls'] = images[:10]
            elif isinstance(images[0], dict):
                result['images_urls'] = [img.get('url', '') for img in images if img.get('url')][:10]
        
        # Prices
        prices = comp.get('prices', {})
        if prices:
            dev_price = prices.get('developerStartingPrice')
            resale_price = prices.get('resaleStartingPrice')
            if dev_price:
                result['developer_start_price'] = dev_price
            if resale_price:
                result['resale_start_price'] = resale_price
        
        # Unit count
        unit_count = comp.get('propertiesCount')
        if unit_count:
            result['unit_count'] = unit_count
        
        # Location
        area_name = comp.get('areaName', '')
        if area_name:
            result['location'] = area_name
        
        return result if result else None
    except Exception:
        return None


db_client.connect()
compounds_col = db_client._db['compounds']

compounds = list(compounds_col.find(
    {'$or': [
        {'description': {'$exists': False}},
        {'amenities': {'$exists': False}},
        {'developer_start_price': {'$exists': False}},
    ]},
    {'_id': 1, 'nawy_url': 1, 'slug': 1, 'nawy_id': 1, 'name': 1}
))

console.print(f"[cyan]Found {len(compounds)} compounds to enrich[/]")

enriched = 0
errors = 0

with Progress(
    SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
    BarColumn(), TextColumn("{task.percentage:>3.0f}%"),
    TextColumn("({task.completed}/{task.total})"),
    TimeElapsedColumn(), console=console
) as progress:
    task = progress.add_task("Enriching compounds...", total=len(compounds))
    for c in compounds:
        url = c.get('nawy_url')
        if not url:
            slug = c.get('slug', '')
            if slug:
                url = f"https://www.nawy.com/compound/{slug}"
        
        if url:
            details = fetch_compound_details(url)
            if details:
                compounds_col.update_one({'_id': c['_id']}, {'$set': details})
                enriched += 1
            else:
                errors += 1
        else:
            errors += 1
        
        progress.update(task, advance=1,
                       description=f"Enriching... ({enriched} done, {errors} err)")

console.print(f"\n[green]Enriched {enriched} compounds[/]")
console.print(f"[yellow]Errors/skipped: {errors}[/]")
db_client.disconnect()
