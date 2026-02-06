"""
Smart Unit/Property Scraper
============================

Scrapes ALL properties from Nawy.com search pages.
Total: ~20,846 units across ~1737 pages

Features:
- Scrapes all property data including payment plans
- Links to compounds and developers
- Saves to MongoDB immediately
- Progress saving with resume capability

Usage:
    python scrape_units_smart.py
    python scrape_units_smart.py --clear  # Clear units and start fresh
"""

import asyncio
import json
import sys
import os
import re
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, parse_qs

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console
from scrapers.base_scraper import BaseScraper
from database.connection import db_client
from utils.data_cleaner import DataCleaner
from config.settings import settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('scraper_units.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

console = Console(force_terminal=True)

# Constants
PROGRESS_FILE = "units_progress.json"
SEARCH_URL = "https://www.nawy.com/search"
TOTAL_PAGES = 1737
UNITS_PER_PAGE = 12


class SmartUnitScraper(BaseScraper):
    """Smart Property/Unit Scraper with comprehensive data extraction."""
    
    def __init__(self):
        super().__init__()
        self.compound_lookup = {}  # name -> {_id, developer_name, developer_id}
        self.progress_file = PROGRESS_FILE
    
    def _save_progress(self, data: Dict):
        """Save progress to checkpoint file."""
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            logger.debug(f"💾 Progress saved")
        except Exception as e:
            logger.error(f"Failed to save progress: {e}")
    
    def _load_progress(self) -> Optional[Dict]:
        """Load progress from checkpoint file."""
        try:
            if os.path.exists(self.progress_file):
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info(f"📂 Loaded progress from {self.progress_file}")
                return data
        except Exception as e:
            logger.error(f"Failed to load progress: {e}")
        return None
    
    def build_compound_lookup(self):
        """Build lookup from compound name to compound details."""
        console.print("   📋 Building compound lookup...")
        
        compounds = db_client._db['compounds'].find({}, {
            'name': 1,
            'nawy_id': 1,
            'developer_name': 1,
            'developer_id': 1
        })
        
        for compound in compounds:
            name = compound.get('name')
            if not name:  # Skip if name is None or empty
                continue
            
            name_lower = name.lower().strip()
            self.compound_lookup[name_lower] = {
                'compound_id': str(compound['_id']),
                'compound_nawy_id': compound.get('nawy_id', ''),
                'developer_name': compound.get('developer_name', ''),
                'developer_id': compound.get('developer_id', '')
            }
        
        console.print(f"   Loaded {len(self.compound_lookup)} compounds for lookup")
    
    async def scrape_unit_urls_from_page(self, page_num: int) -> List[str]:
        """Scrape unit URLs from a search results page."""
        url = f"{SEARCH_URL}?category=property&page_number={page_num}"
        
        if not await self.safe_goto(url):
            return []
        
        await asyncio.sleep(2)
        await self.human_scroll(300)
        
        # Extract from __NEXT_DATA__
        next_data = await self.extract_next_data()
        urls = []
        
        if next_data:
            urls = self._extract_urls_from_next_data(next_data)
        
        if not urls:
            # Fallback to HTML
            html = await self.get_page_content()
            urls = self._extract_urls_from_html(html)
        
        return urls
    
    def _extract_urls_from_next_data(self, next_data: Dict) -> List[str]:
        """Extract unit URLs from __NEXT_DATA__."""
        urls = []
        
        try:
            page_props = next_data.get('props', {}).get('pageProps', {})
            properties = (
                page_props.get('properties') or
                page_props.get('data', {}).get('properties') or
                page_props.get('units') or
                page_props.get('results') or
                []
            )
            
            for prop in properties:
                # Build URL from property data
                prop_id = prop.get('id')
                prop_slug = prop.get('slug') or prop.get('url_slug')
                compound_id = prop.get('compound_id') or prop.get('compound', {}).get('id')
                compound_slug = prop.get('compound_slug') or prop.get('compound', {}).get('slug')
                
                if prop_id and compound_id:
                    url = f"{settings.base_url}/compound/{compound_id}-{compound_slug or 'c'}/property/{prop_id}-{prop_slug or 'p'}"
                    urls.append(url)
                elif prop.get('url'):
                    urls.append(urljoin(settings.base_url, prop['url']))
                    
        except Exception as e:
            logger.debug(f"Error extracting URLs: {e}")
        
        return urls
    
    def _extract_urls_from_html(self, html: str) -> List[str]:
        """Extract unit URLs from HTML."""
        urls = []
        soup = self.parse_html(html)
        
        links = soup.select('a[href*="/property/"]')
        for link in links:
            href = link.get('href', '')
            if '/property/' in href:
                full_url = urljoin(settings.base_url, href)
                urls.append(full_url)
        
        return list(set(urls))
    
    async def scrape_unit_detail(self, url: str) -> Optional[Dict]:
        """Scrape detailed data from a unit page with full HTML parsing."""
        if not await self.safe_goto(url):
            return None
        
        await asyncio.sleep(2)
        await self.human_scroll(400)
        
        try:
            # Get HTML content
            html = await self.get_page_content()
            soup = self.parse_html(html)
            
            # Also try __NEXT_DATA__ for additional data
            next_data = await self.extract_next_data()
            prop_data = {}
            if next_data:
                page_props = next_data.get('props', {}).get('pageProps', {})
                prop_data = (
                    page_props.get('property') or
                    page_props.get('unit') or
                    page_props.get('data', {}).get('property') or
                    {}
                )
            
            # Extract nawy_id from URL
            nawy_id = ''
            match = re.search(r'/property/(\d+)-', url)
            if match:
                nawy_id = match.group(1)
            
            # === EXTRACT PROPERTY TYPE FROM URL ===
            # URL pattern: /property/12345-apartment-for-sale-in-...
            # or /property/12345-villa-for-sale-in-...
            property_type_from_url = ''
            property_types_list = ['apartment', 'duplex', 'villa', 'townhouse', 'twinhouse', 
                                   'chalet', 'penthouse', 'studio', 'office', 'retail', 
                                   'cabin', 'clinic', 'loft', 'pharmacy', 'building', 'administrative']
            
            url_lower = url.lower()
            for pt in property_types_list:
                if f'-{pt}-' in url_lower or url_lower.endswith(f'-{pt}'):
                    property_type_from_url = pt.capitalize()
                    break
            
            # === PARSE HTML ===
            
            # Name/Title
            name = ''
            name_elem = soup.select_one('h1')
            if name_elem:
                name = self.clean_text(name_elem.get_text())
            
            # === EXTRACT PROPERTY TYPE FROM TITLE ===
            # Pattern: "Apartment For Sale In..." or "Villa for sale in..."
            property_type_from_title = ''
            if name:
                name_lower = name.lower()
                for pt in property_types_list:
                    if name_lower.startswith(pt) or f' {pt} ' in name_lower:
                        property_type_from_title = pt.capitalize()
                        break
            
            # === LOCATION - Get from specific elements ===
            # Location is typically in H2 under the title, like "Al Maqsad , New Capital City, Egypt"
            location = ''
            
            # Try to find location from __NEXT_DATA__ first (most reliable)
            if prop_data:
                # Try compound area/city
                compound_data = prop_data.get('compound', {})
                if isinstance(compound_data, dict):
                    area_data = compound_data.get('area', {})
                    city_data = compound_data.get('city', {})
                    compound_name_loc = compound_data.get('name', '')
                    
                    area_name = area_data.get('name', '') if isinstance(area_data, dict) else ''
                    city_name = city_data.get('name', '') if isinstance(city_data, dict) else ''
                    
                    location_parts = []
                    if compound_name_loc:
                        location_parts.append(compound_name_loc)
                    if area_name:
                        location_parts.append(area_name)
                    if city_name and city_name not in location_parts:
                        location_parts.append(city_name)
                    
                    if location_parts:
                        location = ', '.join(location_parts)
                
                # Also try direct location field
                if not location:
                    location = prop_data.get('location', '') or prop_data.get('address', '')
            
            # Fallback to HTML - look for H2 after H1 (location subtitle)
            if not location:
                # Look for the location subtitle (H2 after H1)
                h2_elems = soup.select('h2')
                for h2 in h2_elems:
                    h2_text = self.clean_text(h2.get_text())
                    # Location typically contains city or compound name, not sale type
                    if h2_text and 'Egypt' in h2_text or 'Cairo' in h2_text or 'New Capital' in h2_text:
                        location = h2_text
                        break
                    # Or it contains compound name (ends with area)
                    if h2_text and ',' in h2_text and 'sale' not in h2_text.lower():
                        location = h2_text
                        break
            
            # If still no location, try the breadcrumb or location class
            if not location:
                breadcrumb = soup.select_one('[class*="breadcrumb"], nav a')
                if breadcrumb:
                    location = self.clean_text(breadcrumb.get_text())
            
            # Price
            price = None
            price_elem = soup.select_one('[class*="price"], .price')
            if price_elem:
                price_text = price_elem.get_text()
                price = self.parse_price(price_text)
            
            # === PARSE DETAILS TABLE ===
            details = self._parse_details_table(soup)
            
            # Property type - prioritize URL extraction (most accurate)
            # Priority: 1. URL, 2. Title, 3. Details table, 4. __NEXT_DATA__
            property_type = property_type_from_url  # Most reliable - from URL slug
            
            if not property_type:
                property_type = property_type_from_title  # Second - from page title
            
            if not property_type:
                property_type = details.get('property_type', '')  # Third - from page text
            
            if not property_type:
                # Last resort - try from __NEXT_DATA__
                property_type = prop_data.get('type', '')
                if isinstance(property_type, dict):
                    property_type = property_type.get('name', '')
            
            # Area - with min/max support for ranges
            area = details.get('area')
            area_min = None
            area_max = None
            
            # Try to get area from __NEXT_DATA__ first (more accurate)
            if prop_data:
                # Check for area range
                area_min_data = prop_data.get('area_min') or prop_data.get('min_area')
                area_max_data = prop_data.get('area_max') or prop_data.get('max_area')
                
                if area_min_data and area_max_data and area_min_data != area_max_data:
                    area_min = area_min_data
                    area_max = area_max_data
                    area = None  # Don't duplicate if we have range
                elif not area:
                    area = prop_data.get('area') or prop_data.get('size')
            
            # Reference No
            reference_no = details.get('reference_no', nawy_id)
            
            # NOTE: Price is handled after details parsing with proper priority
            # 1. price_from_details (About section "Price: 7,000,000")
            # 2. __NEXT_DATA__
            # 3. HTML element
            
            # Bedrooms & Bathrooms - prefer details table as it's more accurate
            bedrooms = details.get('bedrooms')
            if bedrooms is None and prop_data:
                bedrooms = prop_data.get('bedrooms')
            
            bathrooms = details.get('bathrooms')
            if bathrooms is None and prop_data:
                bathrooms = prop_data.get('bathrooms')
            
            # Delivery
            delivery_year = details.get('delivery_in')
            if not delivery_year and prop_data:
                delivery_year = prop_data.get('delivery_year')
            
            # Compound
            compound_name = details.get('compound', '')
            if not compound_name and prop_data:
                compound_data = prop_data.get('compound', {})
                compound_name = compound_data.get('name') if isinstance(compound_data, dict) else ''
            
            # Get compound and developer IDs from lookup
            compound_info = {}
            if compound_name:
                compound_info = self.compound_lookup.get(compound_name.lower().strip(), {})
            
            # Sale Type
            sale_type = details.get('sale_type', '')
            if not sale_type and prop_data:
                sale_type = prop_data.get('sale_type', '')
            
            # Finishing
            finishing = details.get('finishing', '')
            if not finishing and prop_data:
                finishing = prop_data.get('finishing', '')
            
            # Floor & View - new fields from details
            floor = details.get('floor', '')
            view_direction = details.get('view', '')
            
            # === PAYMENT INFO FROM DETAILS ===
            down_payment = details.get('down_payment')
            price_from_details = details.get('price')
            remaining_amount = details.get('remaining_amount')
            payment_end_year = details.get('payment_end_year')
            
            # === PRICE MIN/MAX ===
            # Some units have price ranges
            price_min = None
            price_max = None
            if prop_data:
                price_min = prop_data.get('price_min') or prop_data.get('min_price')
                price_max = prop_data.get('price_max') or prop_data.get('max_price')
            
            # === PRICE PRIORITY ===
            # 1. Price from details table (About section has "Price: 7,000,000")
            # 2. __NEXT_DATA__ price
            # 3. HTML price element
            if price_from_details:
                price = price_from_details  # Most accurate - from About section
            elif prop_data:
                prop_price = prop_data.get('price')
                if prop_price and isinstance(prop_price, (int, float)):
                    price = int(prop_price)
            
            # === AMENITIES ===
            amenities = self._parse_amenities(soup)
            if not amenities and prop_data:
                amenities_data = prop_data.get('amenities', [])
                for am in amenities_data:
                    if isinstance(am, dict):
                        amenities.append(am.get('name', ''))
                    else:
                        amenities.append(str(am))
            
            # === COORDINATES ===
            lat, lng = self._extract_coordinates(prop_data, soup)
            
            # === PAYMENT PLAN ===
            payment_plan = await self._parse_payment_plan(soup)
            
            # Add down payment from details if not in payment_plan
            if down_payment and not payment_plan.get('down_payment'):
                payment_plan['down_payment'] = down_payment
            
            # Add remaining amount info
            if remaining_amount:
                payment_plan['remaining_amount'] = remaining_amount
            if payment_end_year:
                payment_plan['payment_end_year'] = payment_end_year
            
            # Fallback to __NEXT_DATA__ for payment plan
            if not payment_plan.get('down_payment') and prop_data:
                extra_payment = self._extract_payment_plan_from_data(prop_data)
                for key, value in extra_payment.items():
                    if key not in payment_plan or not payment_plan[key]:
                        payment_plan[key] = value
            
            # === DESCRIPTION ===
            description = self._parse_description(soup)
            if not description and prop_data:
                description = prop_data.get('description', '')
                if description:
                    description = DataCleaner.html_to_text(description)
            
            # === IMAGES ===
            images = self._extract_images_from_html(soup)
            if not images and prop_data:
                images = self._extract_images(prop_data)
            
            # Build unit dict
            unit = {
                'name': name,
                'nawy_id': nawy_id,
                'reference_no': str(reference_no) if reference_no else '',
                'nawy_url': url,
                
                # Location
                'location': location,
                'lat': lat,
                'lng': lng,
                
                # Compound & Developer linking
                'compound_name': compound_name,
                'compound_nawy_id': prop_data.get('compound', {}).get('id', '') if isinstance(prop_data.get('compound'), dict) else '',
                'compound_id': compound_info.get('compound_id', ''),
                'developer_name': compound_info.get('developer_name', ''),
                'developer_id': compound_info.get('developer_id', ''),
                
                # Property details
                'property_type': property_type,
                'area': area,
                'area_min': area_min,
                'area_max': area_max,
                'price': price,
                'price_min': price_min,
                'price_max': price_max,
                'bedrooms': bedrooms,
                'bathrooms': bathrooms,
                'delivery_year': delivery_year,
                'sale_type': sale_type,
                'finishing': finishing,
                'floor': floor,
                'view': view_direction,
                
                # Amenities
                'amenities': amenities,
                
                # Payment - include both payment_plan object and top-level down_payment
                'down_payment': down_payment,
                'payment_plan': payment_plan,
                
                # Content
                'description': description[:5000] if description else '',
                'images': images,
                
                # Metadata
                'scraped_at': datetime.now(timezone.utc).isoformat(),
            }
            
            # Clean None and empty values
            unit = {k: v for k, v in unit.items() if v is not None and v != '' and v != [] and v != {}}
            
            return unit

            
        except Exception as e:
            logger.error(f"Error scraping unit {url}: {e}")
            return None
    
    def _parse_details_table(self, soup) -> Dict:
        """Parse the details table (Duplex, Reference No, Bedrooms, etc.)"""
        details = {}
        
        try:
            # Get all text from the page
            all_text = soup.get_text(separator=' ')
            
            # Property types to look for
            property_types = ['Apartment', 'Duplex', 'Villa', 'Townhouse', 'Twinhouse', 
                            'Chalet', 'Penthouse', 'Studio', 'Office', 'Retail', 
                            'Cabin', 'Clinic', 'Loft', 'Pharmacy', 'Building', 'Administrative']
            
            for pt in property_types:
                if pt in all_text:
                    details['property_type'] = pt
                    break
            
            # ==== IMPROVED PATTERNS FOR NAWY FORMAT ====
            # Format: "Number Of Bedrooms : 3" or "Bedrooms : 3" or "3 Bedrooms"
            
            # Bedrooms - multiple patterns
            bedroom_patterns = [
                r'Number\s*Of\s*Bedrooms?\s*[:\-]?\s*(\d+)',
                r'Bedrooms?\s*[:\-]?\s*(\d+)',
                r'(\d+)\s*Bedrooms?',
                r'Beds?\s*[:\-]?\s*(\d+)',
                r'(\d+)\s*Beds?',
            ]
            for pattern in bedroom_patterns:
                match = re.search(pattern, all_text, re.IGNORECASE)
                if match:
                    details['bedrooms'] = int(match.group(1))
                    break
            
            # Bathrooms - multiple patterns
            bathroom_patterns = [
                r'Number\s*Of\s*Bathrooms?\s*[:\-]?\s*(\d+)',
                r'Bathrooms?\s*[:\-]?\s*(\d+)',
                r'(\d+)\s*Bathrooms?',
                r'Baths?\s*[:\-]?\s*(\d+)',
                r'(\d+)\s*Baths?',
            ]
            for pattern in bathroom_patterns:
                match = re.search(pattern, all_text, re.IGNORECASE)
                if match:
                    details['bathrooms'] = int(match.group(1))
                    break
            
            # Area - patterns like "Built up area: 145" or "121 m²"
            # NOTE: About section uses "Built up area: 145" format
            area_patterns = [
                r'Built\s*up\s*area\s*[:\-]?\s*(\d+(?:,\d+)?)',  # "Built up area: 145"
                r'Built\s*Up\s*Area\s*[:\-]?\s*(\d+(?:,\d+)?)',  # "Built Up Area : 121"
                r'Area\s*[:\-]?\s*(\d+(?:,\d+)?)\s*(?:m|sqm)?',  # "Area: 121" or "Area: 121 m"
                r'(\d+(?:,\d+)?)\s*m[²2]',  # "121 m²"
                r'(\d+(?:,\d+)?)\s*sqm',  # "121 sqm"
            ]
            for pattern in area_patterns:
                match = re.search(pattern, all_text, re.IGNORECASE)
                if match:
                    area_str = match.group(1).replace(',', '')
                    details['area'] = int(area_str)
                    break
            
            # Reference Number
            ref_patterns = [
                r'Reference\s*No\.?\s*[:\-]?\s*(\d+)',
                r'Ref\.?\s*[:\-]?\s*(\d+)',
                r'Property\s*ID\s*[:\-]?\s*(\d+)',
            ]
            for pattern in ref_patterns:
                match = re.search(pattern, all_text, re.IGNORECASE)
                if match:
                    details['reference_no'] = int(match.group(1))
                    break
            
            # Delivery - patterns like "Delivery : Ready To Move" or "Delivery : 2025"
            delivery_patterns = [
                r'Delivery\s*[:\-]?\s*(Ready\s*To\s*Move)',
                r'Delivery\s*[:\-]?\s*(20\d{2})',
                r'Delivery\s*(?:In|Date)?\s*[:\-]?\s*(20\d{2})',
            ]
            for pattern in delivery_patterns:
                match = re.search(pattern, all_text, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    if value.lower().replace(' ', '') == 'readytomove':
                        details['delivery_in'] = 'Ready To Move'
                    else:
                        try:
                            details['delivery_in'] = int(value)
                        except:
                            details['delivery_in'] = value
                    break
            
            # Finishing - keep EXACT values from Nawy
            # Values: Finished, Not Finished, Semi-Finished, Furnished, Flexi Finished
            finishing_patterns = [
                r'Finishing\s*[:\-]?\s*(Finished|Not\s*Finished|Semi[\-\s]?Finished|Furnished|Flexi\s*Finished|Core\s*(?:and|\&)?\s*Shell)',
            ]
            for pattern in finishing_patterns:
                match = re.search(pattern, all_text, re.IGNORECASE)
                if match:
                    # Keep the exact value as found on the page
                    finishing_val = match.group(1).strip()
                    # Only normalize spacing, not the actual value
                    finishing_val = ' '.join(finishing_val.split())  # normalize whitespace
                    details['finishing'] = finishing_val
                    break

            
            # Floor
            floor_patterns = [
                r'Floor\s*[:\-]?\s*(\w+\s*Floor)',
                r'Floor\s*[:\-]?\s*(\d+)',
            ]
            for pattern in floor_patterns:
                match = re.search(pattern, all_text, re.IGNORECASE)
                if match:
                    details['floor'] = match.group(1).strip()
                    break
            
            # View
            view_patterns = [
                r'View\s*[:\-]?\s*(Bahary|Garden|Pool|Sea|Street|Corner|Main)',
            ]
            for pattern in view_patterns:
                match = re.search(pattern, all_text, re.IGNORECASE)
                if match:
                    details['view'] = match.group(1).strip()
                    break
            
            # Sale Type
            if 'Resale' in all_text:
                details['sale_type'] = 'Resale'
            elif 'Developer Sale' in all_text or 'Primary' in all_text:
                details['sale_type'] = 'Developer Sale'
            
            # Down Payment - patterns like "Down Payment : 3,500,000" or "Down Payment:3500000"
            dp_patterns = [
                r'Down\s*Payment\s*[:\-]?\s*([\d,]+(?:\.\d+)?)',
            ]
            for pattern in dp_patterns:
                match = re.search(pattern, all_text, re.IGNORECASE)
                if match:
                    dp_str = match.group(1).replace(',', '')
                    try:
                        details['down_payment'] = int(float(dp_str))
                    except:
                        pass
                    break
            
            # Price - patterns like "Price : 7,000,000" or "7,000,000 EGP"
            price_patterns = [
                r'Price\s*[:\-]?\s*([\d,]+(?:\.\d+)?)',
                r'([\d,]+)\s*EGP',
            ]
            for pattern in price_patterns:
                match = re.search(pattern, all_text, re.IGNORECASE)
                if match:
                    price_str = match.group(1).replace(',', '')
                    try:
                        details['price'] = int(float(price_str))
                    except:
                        pass
                    break
            
            # Remaining installments - patterns like "Remaining : 3,500,000 Till 2034"
            remaining_patterns = [
                r'Remaining\s*[:\-]?\s*([\d,]+)\s*(?:Till|Until|Over)?\s*(20\d{2})?',
            ]
            for pattern in remaining_patterns:
                match = re.search(pattern, all_text, re.IGNORECASE)
                if match:
                    remaining_str = match.group(1).replace(',', '')
                    try:
                        details['remaining_amount'] = int(remaining_str)
                        if match.group(2):
                            details['payment_end_year'] = int(match.group(2))
                    except:
                        pass
                    break
                        
        except Exception as e:
            logger.debug(f"Error parsing details table: {e}")
        
        return details
    
    def _parse_amenities(self, soup) -> List[str]:
        """Parse amenities section."""
        amenities = []
        
        try:
            # Look for amenities section
            amenities_section = soup.find(string=re.compile(r'Amenities', re.I))
            if amenities_section:
                parent = amenities_section.find_parent(['div', 'section'])
                if parent:
                    items = parent.select('span, li, div')
                    for item in items:
                        text = self.clean_text(item.get_text())
                        if text and text != 'Amenities' and len(text) < 50:
                            amenities.append(text)
            
            # Fallback: look for common amenity icons/labels
            amenity_keywords = ['Pool', 'Gym', 'Parking', 'Security', 'Garden', 
                              'Elevator', 'Balcony', 'Terrace', 'Beach', 'Mall']
            all_text = soup.get_text()
            for keyword in amenity_keywords:
                if keyword in all_text and keyword not in amenities:
                    amenities.append(keyword)
                    
        except Exception as e:
            logger.debug(f"Error parsing amenities: {e}")
        
        return list(set(amenities))[:20]  # Limit and dedupe
    
    def _extract_coordinates(self, prop_data: Dict, soup) -> Tuple[Optional[float], Optional[float]]:
        """Extract lat/lng coordinates."""
        lat, lng = None, None
        
        try:
            # From __NEXT_DATA__
            if prop_data:
                lat = prop_data.get('lat') or prop_data.get('latitude')
                lng = prop_data.get('lng') or prop_data.get('longitude')
                
                # Check compound data
                if not lat and not lng:
                    compound = prop_data.get('compound', {})
                    if isinstance(compound, dict):
                        lat = compound.get('lat') or compound.get('latitude')
                        lng = compound.get('lng') or compound.get('longitude')
            
            # From HTML (look for map data in scripts)
            if not lat or not lng:
                scripts = soup.select('script')
                for script in scripts:
                    if script.string:
                        # Look for lat/lng patterns
                        lat_match = re.search(r'"lat(?:itude)?"\s*:\s*([\d.]+)', script.string)
                        lng_match = re.search(r'"lng|lon(?:gitude)?"\s*:\s*([\d.]+)', script.string)
                        if lat_match and lng_match:
                            lat = float(lat_match.group(1))
                            lng = float(lng_match.group(1))
                            break
                            
        except Exception as e:
            logger.debug(f"Error extracting coordinates: {e}")
        
        return lat, lng
    
    async def _parse_payment_plan(self, soup) -> Dict:
        """Parse payment plan by clicking on the arrow next to Down Payment."""
        payment = {}
        
        try:
            # The payment plan modal opens by clicking on the arrow (>) next to "Down Payment (1/2)"
            # Look for clickable elements in the Payment Plans section
            plan_button = await self.page.query_selector(
                # Try to find the arrow/chevron button or the plan card itself
                '[class*="payment"] [class*="arrow"], '
                '[class*="payment"] [class*="chevron"], '
                '[class*="payment"] svg, '
                '[class*="plan"] > div:has-text("Down Payment"), '
                'div:has-text("EGP Down Payment") >> xpath=..'
            )
            
            if not plan_button:
                # Fallback: try to find any clickable element in payment section
                plan_button = await self.page.query_selector(
                    'text="Down Payment" >> xpath=ancestor::div[contains(@class, "cursor") or @role="button" or contains(@class, "clickable")]'
                )
            
            if not plan_button:
                # Last resort: find the plan card container
                plan_button = await self.page.query_selector(
                    'div:has-text("Original Plan"):has-text("EGP")'
                )
            
            if plan_button:
                await plan_button.click()
                await asyncio.sleep(1.5)
                
                # Get updated HTML after modal opens
                html = await self.get_page_content()
                soup = self.parse_html(html)
                
                # Look for modal content
                modal = soup.select_one('[class*="modal"], [class*="popup"], [class*="dialog"]')
                if modal:
                    modal_text = modal.get_text()
                else:
                    modal_text = soup.get_text()
                
                # Parse payment details
                # Total Price
                total_match = re.search(r'Total\s*Price\s*[:\-]?\s*([\d,]+)\s*EGP', modal_text, re.I)
                if total_match:
                    payment['total_price'] = int(total_match.group(1).replace(',', ''))
                
                # Monthly/Quarterly installment
                monthly_match = re.search(r'([\d,]+)\s*EGP\s*Monthly', modal_text, re.I)
                if monthly_match:
                    payment['monthly_installment'] = int(monthly_match.group(1).replace(',', ''))
                
                quarterly_match = re.search(r'([\d,]+)\s*EGP\s*Quarterly', modal_text, re.I)
                if quarterly_match:
                    payment['quarterly_installment'] = int(quarterly_match.group(1).replace(',', ''))
                
                # Years
                years_match = re.search(r'(\d+)\s*Years?', modal_text, re.I)
                if years_match:
                    payment['installment_years'] = int(years_match.group(1))
                
                # Down Payments
                down_payments = []
                dp_matches = re.findall(r'Down\s*Payment\s*(\d)\s*[:\-]?\s*([\d,]+)\s*EGP', modal_text, re.I)
                for num, amount in dp_matches:
                    down_payments.append({
                        'number': int(num),
                        'amount': int(amount.replace(',', ''))
                    })
                if down_payments:
                    payment['down_payments'] = down_payments
                
                # Total Installments
                installments_match = re.search(r'Total\s*Installments\s*[:\-]?\s*([\d,]+)\s*EGP', modal_text, re.I)
                if installments_match:
                    payment['total_installments'] = int(installments_match.group(1).replace(',', ''))
                
                # Maintenance Fees
                maintenance_match = re.search(r'[Mm]aintenance\s*[Ff]ees?\s*[:\-]?\s*([\d,]+)\s*EGP', modal_text)
                if maintenance_match:
                    payment['maintenance_fees'] = int(maintenance_match.group(1).replace(',', ''))
                
                # Close modal
                close_btn = await self.page.query_selector(
                    'button[class*="close"], [class*="modal"] button, svg[class*="close"]'
                )
                if close_btn:
                    await close_btn.click()
                    await asyncio.sleep(0.5)
                    
        except Exception as e:
            logger.debug(f"Error parsing payment plan: {e}")
        
        return payment
    
    def _extract_payment_plan_from_data(self, prop_data: Dict) -> Dict:
        """Extract payment plan from __NEXT_DATA__."""
        payment = {}
        
        try:
            payment['down_payment'] = prop_data.get('down_payment')
            payment['down_payment_percent'] = prop_data.get('down_payment_percent')
            payment['installment_years'] = prop_data.get('installment_years') or prop_data.get('payment_years')
            payment['monthly_installment'] = prop_data.get('monthly_installment')
            payment['quarterly_installment'] = prop_data.get('quarterly_installment')
            
            plan_data = prop_data.get('payment_plan', {}) or prop_data.get('plan', {})
            if isinstance(plan_data, dict):
                payment['total_price'] = plan_data.get('total_price')
                payment['down_payments'] = plan_data.get('down_payments', [])
                payment['total_installments'] = plan_data.get('total_installments')
                payment['delivery_payment'] = plan_data.get('delivery_payment')
                payment['maintenance_fees'] = plan_data.get('maintenance_fees')
            
            payment = {k: v for k, v in payment.items() if v is not None}
            
        except Exception as e:
            logger.debug(f"Error extracting payment from data: {e}")
        
        return payment
    
    def _parse_description(self, soup) -> str:
        """Parse About section description."""
        description = ''
        
        try:
            # Look for About section
            about_header = soup.find(string=re.compile(r'^About\s', re.I))
            if about_header:
                parent = about_header.find_parent(['div', 'section', 'article'])
                if parent:
                    # Get text after the header
                    paragraphs = parent.find_all(['p', 'div'], recursive=False)
                    texts = []
                    for p in paragraphs:
                        text = self.clean_text(p.get_text())
                        if text and len(text) > 20:
                            texts.append(text)
                    description = ' '.join(texts)
            
            # Fallback: look for description class
            if not description:
                desc_elem = soup.select_one('[class*="description"], [class*="about"]')
                if desc_elem:
                    description = self.clean_text(desc_elem.get_text())
                    
        except Exception as e:
            logger.debug(f"Error parsing description: {e}")
        
        return DataCleaner.html_to_text(description) if description else ''
    
    def _extract_images_from_html(self, soup) -> List[str]:
        """Extract images from HTML."""
        images = []
        
        try:
            # Look for gallery images
            img_tags = soup.select('img[src*="nawy"], img[src*="cloudinary"], img[src*="property"]')
            for img in img_tags:
                src = img.get('src') or img.get('data-src')
                if src and 'logo' not in src.lower() and src not in images:
                    if not src.startswith('http'):
                        src = f"https:{src}" if src.startswith('//') else src
                    images.append(src)
            
            # Also check background images in style
            divs_with_bg = soup.select('[style*="background-image"]')
            for div in divs_with_bg:
                style = div.get('style', '')
                url_match = re.search(r'url\(["\']?([^"\']+)["\']?\)', style)
                if url_match:
                    images.append(url_match.group(1))
                    
        except Exception as e:
            logger.debug(f"Error extracting images: {e}")
        
        return images[:10]
    
    def _extract_images(self, prop_data: Dict) -> List[str]:
        """Extract images from __NEXT_DATA__."""
        images = []
        
        try:
            for field in ['images', 'gallery', 'photos', 'media']:
                img_data = prop_data.get(field, [])
                if isinstance(img_data, list):
                    for img in img_data:
                        url = img.get('url') if isinstance(img, dict) else img
                        if url and url not in images:
                            images.append(url)
            
            main_img = prop_data.get('image') or prop_data.get('main_image')
            if main_img and main_img not in images:
                images.insert(0, main_img)
                
        except Exception as e:
            logger.debug(f"Error extracting images from data: {e}")
        
        return images[:10]


def get_existing_unit_urls() -> Set[str]:
    """Get all unit URLs already in MongoDB."""
    try:
        units = db_client._db['units'].find({}, {'nawy_url': 1})
        return {u.get('nawy_url') for u in units if u.get('nawy_url')}
    except Exception as e:
        logger.error(f"Error getting existing units: {e}")
        return set()


async def scrape_all_units():
    """Main function to scrape all units."""
    
    console.print("\n[bold cyan]🏠 Smart Unit Scraper[/bold cyan]")
    console.print("[dim]Scrapes ALL properties from Nawy.com[/dim]\n")
    
    scraper = SmartUnitScraper()
    
    # Build compound lookup
    scraper.build_compound_lookup()
    
    # Get existing units
    existing_urls = get_existing_unit_urls()
    console.print(f"   Existing units in MongoDB: {len(existing_urls)}")
    
    # Load progress
    progress = scraper._load_progress()
    start_page = 1
    
    if progress:
        start_page = progress.get('last_page', 0) + 1
        console.print(f"   📂 Resuming from page {start_page}")
    
    console.print(f"\n   Total pages: {TOTAL_PAGES}")
    console.print(f"   Starting from page: {start_page}")
    console.print(f"\n   Press Enter to start...")
    input()
    
    # Initialize browser
    await scraper.initialize()
    
    stats = {
        'pages_processed': 0,
        'units_found': 0,
        'units_scraped': 0,
        'units_skipped': 0,
        'units_failed': 0
    }
    
    try:
        for page_num in range(start_page, TOTAL_PAGES + 1):
            logger.info(f"📄 Page {page_num}/{TOTAL_PAGES}")
            
            # Get unit URLs from page
            unit_urls = await scraper.scrape_unit_urls_from_page(page_num)
            stats['units_found'] += len(unit_urls)
            
            logger.info(f"   Found {len(unit_urls)} units on page")
            
            # Scrape each unit
            for i, unit_url in enumerate(unit_urls):
                # Skip if already exists
                if unit_url in existing_urls:
                    stats['units_skipped'] += 1
                    continue
                
                logger.info(f"   [{i+1}/{len(unit_urls)}] Scraping: {unit_url[:80]}...")
                
                unit_data = await scraper.scrape_unit_detail(unit_url)
                
                if unit_data:
                    # Save to MongoDB immediately
                    try:
                        db_client.upsert_unit(unit_data)
                        stats['units_scraped'] += 1
                        existing_urls.add(unit_url)
                        logger.info(f"      ✅ {unit_data.get('name', 'Unknown')[:50]}")
                    except Exception as e:
                        logger.error(f"      MongoDB error: {e}")
                        stats['units_failed'] += 1
                else:
                    stats['units_failed'] += 1
                    logger.warning(f"      ❌ Failed to scrape")
                
                await scraper.random_delay()
            
            stats['pages_processed'] += 1
            
            # Save progress after each page
            scraper._save_progress({
                'last_page': page_num,
                'stats': stats,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
            
            # Log progress every 10 pages
            if page_num % 10 == 0:
                console.print(f"   📊 Progress: {page_num}/{TOTAL_PAGES} pages | {stats['units_scraped']} scraped | {stats['units_skipped']} skipped")
            
            await scraper.random_delay()
        
        console.print(f"\n[bold green]🎉 Done![/bold green]")
        
    except KeyboardInterrupt:
        console.print(f"\n[yellow]⚠️ Interrupted! Progress saved at page {start_page + stats['pages_processed'] - 1}[/yellow]")
    except Exception as e:
        logger.error(f"Error: {e}")
        logger.exception("Details")
    finally:
        await scraper.close()
    
    return stats


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Smart Unit Scraper')
    parser.add_argument('--clear', action='store_true', help='Clear all units from MongoDB before scraping')
    args = parser.parse_args()
    
    console.print("\n" + "=" * 60)
    console.print("[bold blue]    NAWY.COM - SMART UNIT SCRAPER[/bold blue]")
    console.print("[bold blue]    Scrapes ALL properties (~20,846 units)[/bold blue]")
    console.print("=" * 60 + "\n")
    
    # Connect to MongoDB
    console.print("[bold]Connecting to MongoDB...[/bold]")
    if not db_client.connect():
        console.print("[red]❌ Failed to connect to MongoDB[/red]")
        return
    
    stats = db_client.get_collection_stats()
    console.print(f"   Compounds: {stats.get('compounds', 0)}")
    console.print(f"   Developers: {stats.get('developers', 0)}")
    console.print(f"   Units: {stats.get('units', 0)}")
    
    # Clear if requested
    if args.clear:
        console.print("\n[bold yellow]🗑️ Clearing all units from MongoDB...[/bold yellow]")
        try:
            result = db_client._db['units'].delete_many({})
            console.print(f"   Deleted {result.deleted_count} units")
            # Also remove progress file
            if os.path.exists(PROGRESS_FILE):
                os.remove(PROGRESS_FILE)
                console.print(f"   Deleted progress file")
        except Exception as e:
            console.print(f"[red]Error clearing: {e}[/red]")
    
    try:
        # Scrape units
        stats = asyncio.run(scrape_all_units())
        
        if stats:
            console.print(f"\n[bold green]📊 Final Stats:[/bold green]")
            console.print(f"   Pages processed: {stats.get('pages_processed', 0)}")
            console.print(f"   Units found: {stats.get('units_found', 0)}")
            console.print(f"   Units scraped: {stats.get('units_scraped', 0)}")
            console.print(f"   Units skipped: {stats.get('units_skipped', 0)}")
            console.print(f"   Units failed: {stats.get('units_failed', 0)}")
        
        # Show final count
        final_stats = db_client.get_collection_stats()
        console.print(f"\n[bold]Total units in MongoDB: {final_stats.get('units', 0)}[/bold]")
            
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]❌ Error: {e}[/red]")
        logger.exception("Error")
    finally:
        db_client.disconnect()


if __name__ == '__main__':
    main()
