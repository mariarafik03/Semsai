#!/usr/bin/env python3
"""Fix compound fields to match old format expected by Flutter app."""
import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from database.connection import db_client
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn

console = Console(force_terminal=True)

db_client.connect()
compounds_col = db_client._db['compounds']
units_col = db_client._db['units']

compounds = list(compounds_col.find({}))
console.print(f"[cyan]Found {len(compounds)} compounds to fix[/]")

updated = 0
with Progress(
    SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
    BarColumn(), TextColumn("{task.percentage:>3.0f}%"),
    TextColumn("({task.completed}/{task.total})"),
    TimeElapsedColumn(), console=console
) as progress:
    task = progress.add_task("Fixing compounds...", total=len(compounds))
    for c in compounds:
        updates = {}
        
        # 1. area_name -> location
        if not c.get('location') and c.get('area_name'):
            updates['location'] = c['area_name']
        
        # 2. image_url -> images_urls (array)
        if not c.get('images_urls') and c.get('image_url'):
            updates['images_urls'] = [c['image_url']]
        
        # 3. Count units for this compound
        if not c.get('unit_count'):
            count = units_col.count_documents({'compound_id': c['_id']})
            if count == 0:
                # Try matching by nawy_id in the unit's compound_id_nawy
                count = units_col.count_documents({'compound_id_nawy': str(c.get('nawy_id', ''))})
            if count > 0:
                updates['unit_count'] = count
        
        if updates:
            compounds_col.update_one({'_id': c['_id']}, {'$set': updates})
            updated += 1
        
        progress.update(task, advance=1)

console.print(f"\n[green]Updated {updated} compounds[/]")
db_client.disconnect()
