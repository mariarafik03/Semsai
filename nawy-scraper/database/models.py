"""
Pydantic Models matching MongoDB Schemas
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class LayoutStyle(str, Enum):
    MODERN = "modern"
    LUXURY = "luxury"
    MIXED = "mixed"


class DeliveryDelay(str, Enum):
    NONE = "None"
    LOW = "Low"
    HIGH = "High"


class UnitStatus(str, Enum):
    AVAILABLE = "Available"
    SOLD = "Sold"
    RESERVED = "Reserved"


class Amenities(BaseModel):
    """Compound amenities schema."""
    clubhouse: Optional[bool] = None
    gym: Optional[bool] = None
    cafes: Optional[bool] = None
    restaurants: Optional[bool] = None
    parks: Optional[bool] = None
    nightlife_nearby: Optional[bool] = None
    commercial_strip: Optional[bool] = None
    food_court: Optional[bool] = None
    outdoor_pools: Optional[bool] = None
    children_play_area: Optional[bool] = None
    barbecue_area: Optional[bool] = None
    bicycle_lanes: Optional[bool] = None
    jogging_trail: Optional[bool] = None
    # Additional from Nawy
    swimming_pool: Optional[bool] = None
    security_24h: Optional[bool] = None
    private_beach: Optional[bool] = None
    golf_course: Optional[bool] = None
    spa: Optional[bool] = None
    cinema: Optional[bool] = None
    mosque: Optional[bool] = None
    schools: Optional[bool] = None
    medical_center: Optional[bool] = None


class MarketHistoryEntry(BaseModel):
    """Historical market data for a compound."""
    year: int
    avg_sale_price: Optional[float] = None
    avg_rent_price: Optional[float] = None
    occupancy_rate: Optional[float] = None


class CompoundModel(BaseModel):
    """Compound schema matching MongoDB."""
    name: str
    nawy_id: Optional[str] = None  # Nawy's internal ID
    nawy_slug: Optional[str] = None  # URL slug
    nawy_url: Optional[str] = None  # Full URL
    
    description: Optional[str] = None
    location: Optional[str] = None  # e.g., "New Cairo"
    area: Optional[float] = None  # Total area in sqm
    phases: Optional[int] = None
    completed_phases: Optional[int] = None
    
    lat: Optional[float] = None
    lng: Optional[float] = None
    
    # Developer relationship
    developer_name: Optional[str] = None
    developer_id: Optional[str] = None  # MongoDB ObjectId as string
    
    # Enhanced fields
    gated: Optional[bool] = None
    is_gated: Optional[bool] = True
    security_level: Optional[int] = Field(None, ge=1, le=5)
    delivery_year: Optional[int] = None
    layout_style: Optional[LayoutStyle] = None
    
    # Price data
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    price_per_sqm_min: Optional[float] = None
    price_per_sqm_max: Optional[float] = None
    
    # Counts
    unit_count: Optional[int] = None
    available_units: Optional[int] = None
    
    # Media
    images_urls: Optional[List[str]] = []
    video_url: Optional[str] = None
    
    # Amenities
    amenities: Optional[Amenities] = None
    amenities_list: Optional[List[str]] = []  # Simple list format
    
    # Market history
    market_history: Optional[List[MarketHistoryEntry]] = []
    
    # Metadata
    project_status: Optional[str] = None  # under_construction, completed, selling_out
    project_type: Optional[str] = None  # residential, commercial, mixed
    
    # Timestamps
    scraped_at: Optional[datetime] = None
    
    class Config:
        use_enum_values = True


class DeveloperModel(BaseModel):
    """Developer schema matching MongoDB."""
    dev_name: str
    nawy_id: Optional[str] = None
    nawy_slug: Optional[str] = None
    nawy_url: Optional[str] = None
    
    projects_completed: Optional[int] = None
    total_projects: Optional[int] = None
    specialization: Optional[str] = None
    rating: Optional[float] = None
    dev_history: Optional[str] = None
    
    years_active: Optional[int] = None
    google_reviews_score: Optional[float] = 0
    facebook_reviews_score: Optional[float] = 0
    delivery_delays: Optional[DeliveryDelay] = DeliveryDelay.NONE
    
    # Additional from Nawy
    logo_url: Optional[str] = None
    description: Optional[str] = None
    compounds_count: Optional[int] = None
    compounds_list: Optional[List[str]] = []  # Names of compounds
    
    # Contact
    website: Optional[str] = None
    phone: Optional[str] = None
    
    scraped_at: Optional[datetime] = None
    
    class Config:
        use_enum_values = True


class UnitModel(BaseModel):
    """Unit schema matching MongoDB."""
    compound_id: Optional[str] = None  # MongoDB ObjectId as string
    compound_name: Optional[str] = None  # For easier reference
    external_id: Optional[str] = None
    nawy_id: Optional[str] = None
    
    type: str  # apartment, villa, chalet, penthouse, office
    area: Optional[float] = None  # Size in sqm
    price: Optional[float] = None  # Current price
    price_per_sqm: Optional[float] = None
    url: Optional[str] = None
    
    # Details
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    floor_number: Optional[int] = None
    
    delivery_year: Optional[int] = None
    delivery_date: Optional[datetime] = None
    finishing: Optional[str] = None  # fully_finished, semi_finished, core_shell
    view: Optional[str] = None  # garden, street, pool, etc.
    status: Optional[UnitStatus] = UnitStatus.AVAILABLE
    
    # Payment plan
    down_payment: Optional[float] = None
    down_payment_percent: Optional[float] = None
    installment_years: Optional[int] = None
    monthly_installment: Optional[float] = None
    
    # Location
    lat: Optional[float] = None
    lng: Optional[float] = None
    
    # Media
    images_urls: Optional[List[str]] = []
    floor_plan_url: Optional[str] = None
    
    # Amenities specific to unit
    amenities: Optional[List[str]] = []
    
    scraped_at: Optional[datetime] = None
    
    class Config:
        use_enum_values = True


class PriceHistoryModel(BaseModel):
    """Price history schema matching MongoDB."""
    compound_id: str
    compound_name: Optional[str] = None
    year: int
    month: Optional[int] = Field(None, ge=1, le=12)
    
    # Price metrics
    avg_sale_price: Optional[float] = None
    avg_rent_price: Optional[float] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    
    # Market activity
    transaction_volume: Optional[int] = 0
    avg_days_on_market: Optional[float] = None
    
    # Derived metrics
    price_change_rate: Optional[float] = None  # % change from previous period
    price_stability: Optional[float] = None  # 0-1
    occupancy_rate: Optional[float] = None  # 0-1


class ScrapingLog(BaseModel):
    """Scraping audit log."""
    scraper_type: str  # compounds, developers, units
    url: str
    status: str  # success, failed, skipped
    items_scraped: int = 0
    error_message: Optional[str] = None
    duration_seconds: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
