"""
MongoDB Connection and Database Operations
"""
from typing import Optional, Dict, Any, List
from pymongo import MongoClient, UpdateOne
from pymongo.database import Database
from pymongo.collection import Collection
from pymongo.errors import ConnectionFailure, OperationFailure
from datetime import datetime
import logging

from config.settings import settings

logger = logging.getLogger(__name__)


class DatabaseClient:
    """MongoDB client wrapper with connection pooling and helper methods."""
    
    def __init__(self):
        self._client: Optional[MongoClient] = None
        self._db: Optional[Database] = None
    
    def connect(self) -> bool:
        """Establish connection to MongoDB."""
        # Try SRV connection first
        if self._try_connect(settings.mongo_uri, "SRV"):
            return True
        
        # Fallback to direct connection (no DNS SRV lookup)
        logger.warning("⚠️ SRV connection failed, trying direct connection...")
        if self._try_connect(settings.mongo_uri_direct, "Direct"):
            return True
        
        logger.error("❌ All MongoDB connection attempts failed")
        return False
    
    def _try_connect(self, uri: str, conn_type: str) -> bool:
        """Try to connect with a specific URI."""
        try:
            self._client = MongoClient(
                uri,
                serverSelectionTimeoutMS=30000,
                connectTimeoutMS=30000,
                socketTimeoutMS=60000,
                retryWrites=True,
                retryReads=True,
            )
            # Test connection
            self._client.admin.command('ping')
            self._db = self._client[settings.database_name]
            logger.info(f"✅ Connected to MongoDB ({conn_type}): {settings.database_name}")
            return True
        except ConnectionFailure as e:
            logger.warning(f"⚠️ {conn_type} connection failed: {e}")
            return False
        except Exception as e:
            logger.warning(f"⚠️ {conn_type} connection error: {str(e)[:100]}")
            return False
    
    def disconnect(self):
        """Close MongoDB connection."""
        if self._client:
            self._client.close()
            logger.info("🔌 Disconnected from MongoDB")
    
    @property
    def db(self) -> Database:
        """Get database instance."""
        if self._db is None:
            self.connect()
        return self._db
    
    # ==================== COMPOUNDS ====================
    
    def get_compounds(self, filter_query: Dict = None) -> List[Dict]:
        """Get all compounds from database."""
        query = filter_query or {}
        return list(self.db.compounds.find(query))
    
    def get_compound_by_name(self, name: str) -> Optional[Dict]:
        """Find compound by name (case-insensitive)."""
        return self.db.compounds.find_one({
            "name": {"$regex": f"^{name}$", "$options": "i"}
        })
    
    def upsert_compound(self, compound_data: Dict) -> str:
        """Insert or update a compound."""
        compound_data["updated_at"] = datetime.utcnow()
        
        # Use name as unique identifier
        result = self.db.compounds.update_one(
            {"name": compound_data.get("name")},
            {"$set": compound_data},
            upsert=True
        )
        
        if result.upserted_id:
            logger.info(f"➕ Inserted new compound: {compound_data.get('name')}")
            return str(result.upserted_id)
        else:
            logger.info(f"🔄 Updated compound: {compound_data.get('name')}")
            return "updated"
    
    def bulk_upsert_compounds(self, compounds: List[Dict]) -> Dict:
        """Bulk upsert compounds for efficiency."""
        if not compounds:
            return {"inserted": 0, "updated": 0}
        
        operations = []
        for compound in compounds:
            compound["updated_at"] = datetime.utcnow()
            operations.append(
                UpdateOne(
                    {"name": compound.get("name")},
                    {"$set": compound},
                    upsert=True
                )
            )
        
        result = self.db.compounds.bulk_write(operations)
        return {
            "inserted": result.upserted_count,
            "updated": result.modified_count
        }
    
    # ==================== DEVELOPERS ====================
    
    def get_developers(self, filter_query: Dict = None) -> List[Dict]:
        """Get all developers from database."""
        query = filter_query or {}
        return list(self.db.developers.find(query))
    
    def upsert_developer(self, developer_data: Dict) -> str:
        """Insert or update a developer."""
        developer_data["updated_at"] = datetime.utcnow()
        
        result = self.db.developers.update_one(
            {"dev_name": developer_data.get("dev_name")},
            {"$set": developer_data},
            upsert=True
        )
        
        if result.upserted_id:
            logger.info(f"➕ Inserted new developer: {developer_data.get('dev_name')}")
            return str(result.upserted_id)
        else:
            logger.info(f"🔄 Updated developer: {developer_data.get('dev_name')}")
            return "updated"
    
    # ==================== UNITS ====================
    
    def get_units(self, compound_id: str = None) -> List[Dict]:
        """Get units, optionally filtered by compound."""
        query = {"compound_id": compound_id} if compound_id else {}
        return list(self.db.units.find(query))
    
    def upsert_unit(self, unit_data: Dict) -> str:
        """Insert or update a unit."""
        unit_data["updated_at"] = datetime.utcnow()
        
        # Use nawy_url or nawy_id as unique identifier
        if unit_data.get("nawy_url"):
            filter_key = {"nawy_url": unit_data.get("nawy_url")}
        elif unit_data.get("nawy_id"):
            filter_key = {"nawy_id": unit_data.get("nawy_id")}
        else:
            filter_key = {
                "compound_id": unit_data.get("compound_id"),
                "property_type": unit_data.get("property_type"),
                "area": unit_data.get("area"),
                "price": unit_data.get("price")
            }
        
        result = self.db.units.update_one(
            filter_key,
            {"$set": unit_data},
            upsert=True
        )
        
        if result.upserted_id:
            logger.info(f"➕ Inserted new unit: {unit_data.get('name', 'Unknown')[:50]}")
            return str(result.upserted_id)
        else:
            logger.info(f"🔄 Updated unit: {unit_data.get('name', 'Unknown')[:50]}")
            return "updated"
    
    def bulk_upsert_units(self, units: List[Dict]) -> Dict:
        """Bulk upsert units."""
        if not units:
            return {"inserted": 0, "updated": 0}
        
        operations = []
        for unit in units:
            unit["updated_at"] = datetime.utcnow()
            filter_key = {"url": unit.get("url")} if unit.get("url") else {
                "compound_id": unit.get("compound_id"),
                "type": unit.get("type"),
                "area": unit.get("area")
            }
            operations.append(
                UpdateOne(filter_key, {"$set": unit}, upsert=True)
            )
        
        result = self.db.units.bulk_write(operations)
        return {
            "inserted": result.upserted_count,
            "updated": result.modified_count
        }
    
    # ==================== PRICE HISTORY ====================
    
    def add_price_history(self, price_data: Dict) -> str:
        """Add price history entry."""
        price_data["created_at"] = datetime.utcnow()
        result = self.db.price_history.insert_one(price_data)
        return str(result.inserted_id)
    
    # ==================== SCRAPING LOG ====================
    
    def log_scrape(self, log_data: Dict):
        """Log scraping activity for audit trail."""
        log_data["timestamp"] = datetime.utcnow()
        self.db.scraping_log.insert_one(log_data)
    
    # ==================== ANALYTICS ====================
    
    def clear_collection(self, collection_name: str) -> int:
        """Clear all documents from a collection. Returns count of deleted docs."""
        result = self.db[collection_name].delete_many({})
        logger.warning(f"🗑️ Cleared {result.deleted_count} documents from {collection_name}")
        return result.deleted_count
    
    def clear_compounds(self) -> int:
        """Clear all compounds from the database."""
        return self.clear_collection("compounds")
    
    def get_collection_stats(self) -> Dict:
        """Get counts for all collections."""
        return {
            "compounds": self.db.compounds.count_documents({}),
            "developers": self.db.developers.count_documents({}),
            "units": self.db.units.count_documents({}),
            "price_history": self.db.price_history.count_documents({}),
        }


# Global client instance
db_client = DatabaseClient()


def get_database() -> Database:
    """Get database instance (convenience function)."""
    return db_client.db
