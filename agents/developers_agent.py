import os
from dotenv import load_dotenv
from pymongo import MongoClient
from state import AgentState
CLASS_RANK = {
    "A+": 5,
    "A": 4,
    "B": 3,
    "C": 2,
    "D": 1
}

def get_top_developers_by_score(state: AgentState, limit_count: int = 5):

    candidate_compounds = state.get("candidate_compounds", [])
    if not candidate_compounds:
        print("No candidate compounds found.")
        return []

    compound_ids = [
        comp.get("compound_id")
        for comp in candidate_compounds
        if comp.get("compound_id")
    ]

    if not compound_ids:
        print("No valid compound IDs found.")
        return []

    load_dotenv()
    uri = os.getenv("MONGO_URI")
    if not uri:
        print("Missing MONGO_URI")
        return []

    import certifi
    client = MongoClient(
        uri,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=5000
    )

    try:
        db = client.get_default_database()

        developer_ids = db["compounds"].distinct(
            "developer_id",
            {"_id": {"$in": compound_ids}}
        )

        if not developer_ids:
            print("No developers found for candidate compounds.")
            return []

        pipeline = [
            {"$match": {"_id": {"$in": developer_ids}}},

            # Convert class to numeric score
            {
                "$addFields": {
                    "class_score": {
                        "$switch": {
                            "branches": [
                                {"case": {"$eq": ["$Developer_Class", "A+"]}, "then": 5},
                                {"case": {"$eq": ["$Developer_Class", "A"]},  "then": 4},
                                {"case": {"$eq": ["$Developer_Class", "B"]},  "then": 3},
                                {"case": {"$eq": ["$Developer_Class", "C"]},  "then": 2},
                                {"case": {"$eq": ["$Developer_Class", "D"]},  "then": 1},
                            ],
                            "default": 0
                        }
                    }
                }
            },

            # Count how many of the candidate compounds belong to this developer
            {
                "$lookup": {
                    "from": "compounds",
                    "localField": "_id",
                    "foreignField": "developer_id",
                    "pipeline": [
                        {"$match": {"_id": {"$in": compound_ids}}},
                        {"$project": {"name": 1}}
                    ],
                    "as": "matched_compounds"
                }
            },

            {
                "$addFields": {
                    "compound_count": {"$size": "$matched_compounds"},
                    "compound_names": "$matched_compounds.name"
                }
            },

            # Sort by class score DESC, then by compound count DESC
            {
                "$sort": {
                    "class_score": -1,
                    "compound_count": -1
                }
            },

            {"$limit": limit_count},

            {
                "$project": {
                    "_id": 0,
                    "developer_id": "$_id",
                    "name": 1,
                    "Developer_Class": 1,
                    "class_score": 1,
                    "compound_count": 1,
                    "compound_names": 1,
                    "description": 1,
                    "website": 1
                }
            }
        ]

        return list(db["developers"].aggregate(pipeline))

    except Exception as e:
        print(f"Error fetching developers: {e}")
        return []
    finally:
        client.close()



def developers_agent(state: AgentState):
    
    print("\n--- Developer Agent ---")
    
    limit_count = 5
    top_developers = get_top_developers_by_score(state, limit_count)
    
    state["top_developers"] = top_developers
    

    if top_developers:
        print(f"\nTop {len(top_developers)} Developers (Ranked by Class):\n")
        print("=" * 80)
        
        for idx, dev in enumerate(top_developers, 1):
            print(f"\n{idx}. {dev.get('name', 'Unknown')}")
            print(f"   Developer Class: {dev.get('Developer_Class', 'N/A')}")
            print(f"   Class Score: {dev.get('class_score', 0)}")
            print(f"   Matching Compounds: {dev.get('compound_count', 0)}")
            compounds = dev.get("compound_names", [])
            if compounds:
                print("   Their Compounds:")
                for c in compounds:
                    print(f"      • {c}")

            
    else:
        print("No developers found to display.")
    
    return state