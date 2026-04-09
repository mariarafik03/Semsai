"""
Link Compounds to Developers & Fix HTML Descriptions
=====================================================

This script:
1. Links each compound to its developer using compound_ids from developers collection
2. Converts HTML descriptions to plain text for compounds that still have HTML

Usage:
    python link_compounds_developers.py
"""

import sys
import os
import re
import logging
from datetime import datetime

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from database.connection import db_client
from utils.data_cleaner import DataCleaner

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('link_compounds.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

console = Console(force_terminal=True)


def has_html_tags(text: str) -> bool:
    """Check if text contains HTML tags."""
    if not text:
        return False
    # Look for common HTML patterns
    return bool(re.search(r'<[a-zA-Z][^>]*>', text))


def build_developer_lookup():
    """Build a lookup dictionary from compound_id to developer info."""
    console.print("\n[bold cyan]📋 Building developer lookup...[/bold cyan]")
    
    developers = db_client._db['developers'].find({}, {
        'dev_name': 1,
        '_id': 1,
        'nawy_id': 1,
        'compound_ids': 1,
        'compound_names': 1
    })
    
    # compound_id -> {developer_id, developer_name, developer_nawy_id}
    lookup = {}
    dev_count = 0
    
    for dev in developers:
        dev_count += 1
        dev_info = {
            'developer_id': str(dev['_id']),
            'developer_name': dev.get('dev_name', ''),
            'developer_nawy_id': dev.get('nawy_id', '')
        }
        
        # Map by compound_ids
        compound_ids = dev.get('compound_ids', [])
        for cid in compound_ids:
            lookup[str(cid)] = dev_info
        
        # Also map by compound names (backup)
        compound_names = dev.get('compound_names', [])
        for cname in compound_names:
            if cname:
                lookup[f"name:{cname.lower().strip()}"] = dev_info
    
    console.print(f"   Loaded {dev_count} developers")
    console.print(f"   Created {len(lookup)} lookup entries")
    
    return lookup


def link_compounds_to_developers(lookup: dict) -> dict:
    """Link compounds to their developers with progress saving."""
    console.print("\n[bold cyan]🔗 Linking compounds to developers...[/bold cyan]")
    
    # Load progress if exists
    progress_file = "link_progress.json"
    processed_ids = set()
    
    if os.path.exists(progress_file):
        try:
            import json
            with open(progress_file, 'r', encoding='utf-8') as f:
                progress_data = json.load(f)
                processed_ids = set(progress_data.get('processed_ids', []))
                console.print(f"   📂 Loaded progress: {len(processed_ids)} already processed")
        except:
            pass
    
    compounds = db_client._db['compounds'].find({}, {
        'name': 1,
        'nawy_id': 1,
        'developer_id': 1,
        'developer_name': 1
    })
    
    stats = {
        'total': 0,
        'already_linked': 0,
        'newly_linked': 0,
        'not_found': 0,
        'skipped_progress': 0
    }
    
    compounds_list = list(compounds)
    console.print(f"   Total compounds to process: {len(compounds_list)}")
    
    try:
        for i, compound in enumerate(compounds_list):
            compound_id_str = str(compound['_id'])
            stats['total'] += 1
            
            # Skip if already processed in previous run
            if compound_id_str in processed_ids:
                stats['skipped_progress'] += 1
                continue
            
            nawy_id = compound.get('nawy_id', '')
            compound_name = compound.get('name', '')
            
            # Skip if already has developer_id
            if compound.get('developer_id'):
                stats['already_linked'] += 1
                processed_ids.add(compound_id_str)
                continue
            
            # Try to find developer
            dev_info = None
            
            # First try by compound_id
            if nawy_id:
                dev_info = lookup.get(str(nawy_id))
            
            # Fallback to name
            if not dev_info and compound_name:
                dev_info = lookup.get(f"name:{compound_name.lower().strip()}")
            
            if dev_info:
                # Update in database
                db_client._db['compounds'].update_one(
                    {'_id': compound['_id']},
                    {'$set': {
                        'developer_id': dev_info['developer_id'],
                        'developer_name': dev_info['developer_name'],
                        'developer_nawy_id': dev_info['developer_nawy_id'],
                        'updated_at': datetime.utcnow()
                    }}
                )
                stats['newly_linked'] += 1
                logger.info(f"   [{i+1}/{len(compounds_list)}] Linked: {compound_name} → {dev_info['developer_name']}")
            else:
                stats['not_found'] += 1
                logger.debug(f"   Developer not found for: {compound_name} (id: {nawy_id})")
            
            processed_ids.add(compound_id_str)
            
            # Save progress every 50 compounds
            if (i + 1) % 50 == 0:
                _save_link_progress(progress_file, processed_ids)
                console.print(f"   💾 Progress saved: {len(processed_ids)} processed")
    
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Interrupted! Saving progress...[/yellow]")
        _save_link_progress(progress_file, processed_ids)
        raise
    finally:
        # Save final progress
        _save_link_progress(progress_file, processed_ids)
    
    return stats


def _save_link_progress(progress_file: str, processed_ids: set):
    """Save linking progress to file."""
    import json
    try:
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump({
                'processed_ids': list(processed_ids),
                'timestamp': datetime.utcnow().isoformat()
            }, f)
    except Exception as e:
        logger.error(f"Failed to save progress: {e}")


def fix_html_descriptions() -> dict:
    """Convert HTML descriptions to plain text."""
    console.print("\n[bold cyan]📝 Fixing HTML descriptions...[/bold cyan]")
    
    # Find compounds with HTML in description
    compounds = db_client._db['compounds'].find(
        {'description': {'$regex': '<[a-zA-Z]', '$options': 'i'}},
        {'name': 1, 'description': 1}
    )
    
    stats = {
        'total_checked': 0,
        'html_found': 0,
        'fixed': 0
    }
    
    compounds_list = list(compounds)
    stats['html_found'] = len(compounds_list)
    
    console.print(f"   Found {stats['html_found']} compounds with HTML descriptions")
    
    for compound in compounds_list:
        stats['total_checked'] += 1
        
        description = compound.get('description', '')
        
        if has_html_tags(description):
            # Convert to plain text
            plain_text = DataCleaner.html_to_text(description)
            
            # Update in database
            db_client._db['compounds'].update_one(
                {'_id': compound['_id']},
                {'$set': {
                    'description': plain_text[:5000],
                    'updated_at': datetime.utcnow()
                }}
            )
            stats['fixed'] += 1
            logger.info(f"   Fixed: {compound.get('name', 'Unknown')}")
    
    return stats


def main():
    console.print("\n" + "=" * 60)
    console.print("[bold blue]    LINK COMPOUNDS TO DEVELOPERS[/bold blue]")
    console.print("[bold blue]    & FIX HTML DESCRIPTIONS[/bold blue]")
    console.print("=" * 60 + "\n")
    
    # Connect to MongoDB
    console.print("[bold]Connecting to MongoDB...[/bold]")
    if not db_client.connect():
        console.print("[red]❌ Failed to connect to MongoDB[/red]")
        return
    
    # Show current stats
    stats = db_client.get_collection_stats()
    console.print(f"   Compounds: {stats.get('compounds', 0)}")
    console.print(f"   Developers: {stats.get('developers', 0)}")
    
    try:
        # Step 1: Build developer lookup
        lookup = build_developer_lookup()
        
        # Step 2: Link compounds to developers
        link_stats = link_compounds_to_developers(lookup)
        
        console.print("\n[bold green]🔗 Linking Results:[/bold green]")
        console.print(f"   Total compounds: {link_stats['total']}")
        console.print(f"   Already linked: {link_stats['already_linked']}")
        console.print(f"   Newly linked: {link_stats['newly_linked']}")
        console.print(f"   Not found: {link_stats['not_found']}")
        
        # Step 3: Fix HTML descriptions
        html_stats = fix_html_descriptions()
        
        console.print("\n[bold green]📝 HTML Fix Results:[/bold green]")
        console.print(f"   Found with HTML: {html_stats['html_found']}")
        console.print(f"   Fixed: {html_stats['fixed']}")
        
        console.print("\n[bold green]🎉 Done![/bold green]")
        
    except Exception as e:
        console.print(f"\n[red]❌ Error: {e}[/red]")
        logger.exception("Error")
    finally:
        db_client.disconnect()


if __name__ == '__main__':
    main()
