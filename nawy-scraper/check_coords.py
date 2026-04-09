import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from database.connection import db_client
db_client.connect()
col = db_client._db['compounds']
c = col.find_one({'area_name': 'New Cairo'})
name = c.get('name', '')
lat = c.get('lat')
lng = c.get('lng')
print(f"Compound: {name}")
print(f"  lat={lat}, lng={lng}")
print(f"  Cairo should be lat~30.0, lng~31.2")
if lat and lng:
    if lat > lng:
        print("  => lat > lng => SWAPPED!")
    else:
        print("  => Looks correct")
