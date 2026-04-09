
import asyncio
import os
import sys
import logging
from rich.console import Console

# Add current directory to path
sys.path.append(os.getcwd())

from scrape_units_v2 import UnitScraperV2, db_client

logging.basicConfig(level=logging.INFO)

async def test_skyline_unit():
    url = "https://www.nawy.com/compound/713-skyline/property/50971-studio-for-sale-in-skyline-in-new-cairo-by-morshedy-group"
    
    scraper = UnitScraperV2()
    db_client.connect()
    await scraper.initialize()
    scraper.build_compound_lookup()
    
    print(f"\n--- Scraping: {url} ---")
    unit = await scraper.scrape_unit(url)
    
    if unit:
        print("\n✅ Scraped Successfully!")
        print(f"Name: {unit.get('name')}")
        print(f"Type: {unit.get('property_type')} (Expected: Studio)")
        print(f"Bedrooms: {unit.get('bedrooms')} (Expected: 0, 1, or None)")
        print(f"Bathrooms: {unit.get('bathrooms')} (Expected: 1)")
        print(f"Payment Plans: {len(unit.get('payment_plans', []))} found")
        if unit.get('payment_plans'):
             print(f"First Plan: {unit['payment_plans'][0]['name']}")
             print(f"Total Price: {unit['payment_plans'][0].get('total_price')}")
    else:
        print("\n❌ Failed to scrape unit")
        
    await scraper.close()
    db_client.disconnect()

if __name__ == "__main__":
    asyncio.run(test_skyline_unit())
