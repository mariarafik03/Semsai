import os
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId
import certifi
from main_helpers import ask_ollama

def extract_unit_type_from_description(description: str) -> str:
    """
    Use Ollama to extract the unit type from the description.
    Returns the unit type (e.g., 'Studio', 'Apartment', 'Villa', 'Penthouse', etc.)
    """
    prompt = f"""
You are a real estate expert. Extract the unit type from the following property description.

Description: {description}

The unit type should be one of these common types:
- Studio
- Apartment
- Duplex
- Penthouse
- Villa
- Townhouse
- Chalet
- Twin House
- Standalone Villa
- Office
- Shop
- Clinic
- Warehouse

Return ONLY the unit type in one or two words, nothing else. If you cannot determine it clearly, return "Apartment" as default.

Unit Type:"""
    
    return ask_ollama(prompt)


def add_unit_type_to_properties():
    """
    Main function to add unit_type to all units in the database
    by extracting it from the description field.
    """
    load_dotenv()
    uri = os.getenv("MONGO_URI")
    if not uri:
        print("❌ No MONGO_URI found in environment")
        return
    
    client = MongoClient(uri, tlsCAFile=certifi.where())
    
    try:
        db = client.get_default_database()
        # Use the 'units' collection as identified in the database
        units_collection = db["units"]
        
        # Find all units that don't have unit_type yet
        query = {"unit_type": {"$exists": False}}
        count = units_collection.count_documents(query)
        print(f"🔍 Found {count} units without unit_type")
        
        if count == 0:
            print("✅ All units already have unit_type!")
            return
        
        units_without_type = units_collection.find(query)
        
        updated_count = 0
        failed_count = 0
        
        for idx, unit in enumerate(units_without_type, 1):
            try:
                description = unit.get("description", "")
                unit_id = unit.get("_id")
                unit_name = unit.get("name", "Unknown")
                
                if not description:
                    print(f"⚠️  [{idx}/{count}] No description for {unit_name}, skipping...")
                    continue
                
                # Extract unit type using Ollama
                print(f"🔄 [{idx}/{count}] Processing: {unit_name[:50]}...")
                unit_type = extract_unit_type_from_description(description)
                
                # Update the unit in the database
                result = units_collection.update_one(
                    {"_id": unit_id},
                    {"$set": {"unit_type": unit_type}}
                )
                
                if result.modified_count > 0:
                    updated_count += 1
                    print(f"✅ [{idx}/{count}] Updated '{unit_name[:40]}...' → unit_type: '{unit_type}'")
                else:
                    failed_count += 1
                    print(f"⚠️  [{idx}/{count}] Failed to update '{unit_name[:40]}...'")
                
            except Exception as e:
                failed_count += 1
                print(f"❌ [{idx}/{count}] Error processing unit: {e}")
        
        print("\n" + "="*80)
        print(f"📊 Summary:")
        print(f"   Total processed: {count}")
        print(f"   Successfully updated: {updated_count}")
        print(f"   Failed: {failed_count}")
        print("="*80)
        
    finally:
        client.close()


def add_unit_type_to_specific_property(unit_id_str: str):
    """
    Add unit_type to a specific unit by its ID.
    """
    load_dotenv()
    uri = os.getenv("MONGO_URI")
    if not uri:
        print("❌ No MONGO_URI found in environment")
        return
    
    client = MongoClient(uri, tlsCAFile=certifi.where())
    
    try:
        db = client.get_default_database()
        units_collection = db["units"]
        
        # Try both ObjectId and plain string as ID
        try:
            target_id = ObjectId(unit_id_str)
        except:
            target_id = unit_id_str

        unit = units_collection.find_one({"_id": target_id})
        
        if not unit:
            print(f"❌ Unit with ID {unit_id_str} not found in 'units' collection")
            return
        
        description = unit.get("description", "")
        unit_name = unit.get("name", "Unknown")
        
        if not description:
            print(f"⚠️  No description found for this unit")
            return
        
        print(f"🔄 Processing: {unit_name}")
        print(f"📝 Description: {description[:100]}...")
        
        # Extract unit type
        unit_type = extract_unit_type_from_description(description)
        
        # Update the database
        result = units_collection.update_one(
            {"_id": target_id},
            {"$set": {"unit_type": unit_type}}
        )
        
        if result.modified_count > 0:
            print(f"✅ Successfully updated unit_type to: '{unit_type}'")
        else:
            print(f"⚠️  No changes made (unit_type may already be: '{unit_type}')")
        
        # Show the updated unit
        updated_unit = units_collection.find_one({"_id": target_id})
        print(f"\n📋 Updated unit:")
        print(f"   Name: {updated_unit.get('name')}")
        print(f"   Unit Type: {updated_unit.get('unit_type')}")
        
    finally:
        client.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--all":
            print("\nUpdating all units...\n")
            add_unit_type_to_properties()
        else:
            add_unit_type_to_specific_property(sys.argv[1])
    else:
        print("Usage:")
        print("  python3 update_unit_types.py --all             # Update all units")
        print("  python3 update_unit_types.py <unit_id>         # Update a specific unit")
        print("\nTesting with one unit first as a default...")
        add_unit_type_to_specific_property("69835f2d6337dae46a5ac3d5")