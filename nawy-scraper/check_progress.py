import json

f = open('scraping_progress.json', 'r', encoding='utf-8')
d = json.load(f)
f.close()

print(f"URLs: {len(d.get('compound_urls', []))}")
print(f"Scraped: {len(d.get('scraped_compounds', []))}")
print(f"Last Index: {d.get('last_scraped_index', 0)}")
