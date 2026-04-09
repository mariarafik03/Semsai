#!/usr/bin/env python3
"""Clean HTML from all developer descriptions."""
import re
from database.connection import db_client

db_client.connect()
col = db_client._db['developers']

updated = 0
for dev in col.find({'description': {'$exists': True, '$ne': ''}}):
    desc = dev.get('description', '')
    if not desc:
        continue
    clean = re.sub(r'<[^>]+>', ' ', desc)
    clean = re.sub(r'\s+', ' ', clean).strip()
    clean = clean.replace('&amp;', '&').replace('&nbsp;', ' ')
    clean = clean.replace('&#39;', "'").replace('&quot;', '"')
    if clean != desc:
        col.update_one({'_id': dev['_id']}, {'$set': {'description': clean}})
        updated += 1

print(f'Cleaned {updated} developer descriptions')

sample = col.find_one({})
print(f"Sample: {sample.get('description','')[:200]}")

db_client.disconnect()
