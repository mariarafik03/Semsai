#!/usr/bin/env python3
"""
Nawy Unit Scraper v2 - Complete Rewrite
Scrapes ALL properties from Nawy.com with comprehensive data extraction.

Fields extracted:
- Name, Location, Price, Max Price
- Property Type, Area (min/max), Bedrooms, Bathrooms
- Delivery Year, Compound, Sale Type, Finishing
- Amenities, Payment Plans (with modal interaction)
- Description, Coordinates (lat/lng), Gallery Images
"""

import asyncio
import json
import os
import re
import logging
import argparse
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from rich.console import Console
from rich.panel import Panel

# Local imports
from scrapers.base_scraper import BaseScraper
from database.connection import db_client
from utils.data_cleaner import DataCleaner
from config.settings import settings

# Setup
console = Console()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

PROGRESS_FILE = "units_progress_v2.json"


class UnitScraperV2(BaseScraper):
    """Comprehensive unit scraper with full data extraction."""
    
    def __init__(self):
        super().__init__()
        self.compound_lookup = {}
        self.base_url = settings.base_url
    
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
            if not name:
                continue
            
            name_lower = name.lower().strip()
            self.compound_lookup[name_lower] = {
                'compound_id': str(compound['_id']),
                'compound_nawy_id': compound.get('nawy_id', ''),
                'developer_name': compound.get('developer_name', ''),
                'developer_id': compound.get('developer_id', '')
            }
        
        console.print(f"   ✅ Loaded {len(self.compound_lookup)} compounds for lookup")
    
    async def get_unit_urls_from_page(self, page_num: int) -> List[str]:
        """Get all unit URLs from a search results page."""
        url = f"{self.base_url}/search?category=property&page_number={page_num}"
        
        if not await self.safe_goto(url):
            return []
        
        await asyncio.sleep(2)
        await self.human_scroll(300)
        
        # Extract URLs from __NEXT_DATA__
        next_data = await self.extract_next_data()
        urls = []
        
        if next_data:
            page_props = next_data.get('props', {}).get('pageProps', {})
            properties = page_props.get('properties', []) or page_props.get('data', {}).get('properties', [])
            
            for prop in properties:
                slug = prop.get('slug', '')
                if slug:
                    urls.append(f"{self.base_url}{slug}")
        
        # Fallback: parse HTML
        if not urls:
            html = await self.get_page_content()
            soup = self.parse_html(html)
            
            for link in soup.select('a[href*="/property/"]'):
                href = link.get('href', '')
                if '/property/' in href:
                    full_url = urljoin(self.base_url, href)
                    if full_url not in urls:
                        urls.append(full_url)
        
        return list(set(urls))
    
    async def scrape_unit(self, url: str) -> Optional[Dict]:
        """
        Scrape a single unit page with comprehensive data extraction.
        """
        if not await self.safe_goto(url):
            return None
        
        await asyncio.sleep(2)
        
        try:
            # Get HTML content
            html = await self.get_page_content()
            soup = self.parse_html(html)
            
            # Also get __NEXT_DATA__ for reliable data
            next_data = await self.extract_next_data()
            prop_data = self._get_property_from_next_data(next_data)
            
            # Extract nawy_id from URL
            nawy_id = self._extract_id_from_url(url)
            
            # === 1. BASIC INFO ===
            name = self._extract_name(soup, prop_data)
            location = self._extract_location(soup, prop_data)
            
            # === 2. PRICING ===
            price, max_price = self._extract_prices(soup, prop_data)
            
            # === 3. PROPERTY DETAILS TABLE ===
            details = self._extract_details_table(soup, prop_data)
            
            # === 4. COMPOUND LINKING ===
            compound_name = details.get('compound_name', '')
            compound_info = self._get_compound_info(compound_name)
            
            # === 5. AMENITIES ===
            amenities = self._extract_amenities(soup, prop_data)
            
            # === 6. COORDINATES ===
            lat, lng = self._extract_coordinates(prop_data, soup)
            
            # === 7. PAYMENT PLANS ===
            payment_plans = await self._extract_payment_plans(prop_data)
            
            # === 8. DESCRIPTION ===
            description = self._extract_description(soup, prop_data)
            
            # === 9. IMAGES ===
            images = self._extract_images(prop_data, soup)
            
            # Build unit document
            unit = {
                'name': name,
                'nawy_id': nawy_id,
                'nawy_url': url,
                'location': location,
                
                # Pricing
                'price': price,
                'max_price': max_price,
                
                # Property details
                'property_type': details.get('property_type'),
                'area_min': details.get('area_min'),
                'area_max': details.get('area_max'),
                'bedrooms': details.get('bedrooms'),
                'bathrooms': details.get('bathrooms'),
                'delivery_year': details.get('delivery_year'),
                'sale_type': details.get('sale_type'),
                'finishing': details.get('finishing'),
                
                # Compound & Developer
                'compound_name': compound_name,
                'compound_id': compound_info.get('compound_id', ''),
                'compound_nawy_id': compound_info.get('compound_nawy_id', ''),
                'developer_name': compound_info.get('developer_name', ''),
                'developer_id': compound_info.get('developer_id', ''),
                
                # Other data
                'amenities': amenities,
                'lat': lat,
                'lng': lng,
                'payment_plans': payment_plans,
                'description': description,
                'images': images,
                
                # Metadata
                'scraped_at': datetime.now(timezone.utc).isoformat(),
            }
            
            # Remove None values
            unit = {k: v for k, v in unit.items() if v is not None and v != '' and v != [] and v != {}}
            
            return unit
            
        except Exception as e:
            logger.error(f"Error scraping unit {url}: {e}")
            return None
    
    def _get_property_from_next_data(self, next_data: Optional[Dict]) -> Dict:
        """Extract property data from __NEXT_DATA__."""
        if not next_data:
            return {}
        
        page_props = next_data.get('props', {}).get('pageProps', {})
        return (
            page_props.get('property') or
            page_props.get('unit') or
            page_props.get('data', {}).get('property') or
            {}
        )
    
    def _extract_id_from_url(self, url: str) -> str:
        """Extract nawy_id from URL."""
        match = re.search(r'/property/(\d+)-', url)
        return match.group(1) if match else ''
    
    def _extract_name(self, soup: BeautifulSoup, prop_data: Dict) -> str:
        """Extract property name/title."""
        # From HTML - H1 tag
        h1 = soup.select_one('h1')
        if h1:
            return self.clean_text(h1.get_text())
        
        # From __NEXT_DATA__
        return prop_data.get('name') or prop_data.get('title') or ''
    
    def _extract_location(self, soup: BeautifulSoup, prop_data: Dict) -> str:
        """Extract location string."""
        # Look for location under title
        location_elem = soup.select_one('h1 + div, h1 ~ p, [class*="location"]')
        if location_elem:
            text = self.clean_text(location_elem.get_text())
            # Check if it looks like a location (contains Egypt or comma-separated)
            if 'Egypt' in text or ', ' in text:
                return text
        
        # From __NEXT_DATA__
        location_data = prop_data.get('location', {})
        if isinstance(location_data, dict):
            return location_data.get('name', '')
        
        return prop_data.get('area_name', '')
    
    def _extract_prices(self, soup: BeautifulSoup, prop_data: Dict) -> Tuple[Optional[int], Optional[int]]:
        """Extract price and max_price."""
        price = None
        max_price = None
        
        # From HTML - look for price patterns
        all_text = soup.get_text()
        
        # Pattern: "16,968,000 EGP" or "Prices Start From 16,968,000 EGP"
        price_matches = re.findall(r'([\d,]+)\s*EGP', all_text)
        if price_matches:
            prices = [int(p.replace(',', '')) for p in price_matches]
            if prices:
                price = min(prices)
                if len(prices) > 1:
                    max_price = max(prices)
                    if max_price == price:
                        max_price = None
        
        # From __NEXT_DATA__
        if not price:
            price = prop_data.get('price') or prop_data.get('min_price')
            max_price = prop_data.get('max_price')
        
        return price, max_price
    
    def _extract_details_table(self, soup: BeautifulSoup, prop_data: Dict) -> Dict:
        """Extract all details from property table."""
        details = {}
        all_text = soup.get_text()
        
        # === Property Type ===
        # Priority 1: Check __NEXT_DATA__ property_type
        ptype_data = prop_data.get('property_type')
        if isinstance(ptype_data, dict):
            details['property_type'] = ptype_data.get('name')
        elif ptype_data:
            details['property_type'] = str(ptype_data)
            
        # Priority 2: Check H1 Title
        if not details.get('property_type'):
            h1 = soup.select_one('h1')
            if h1:
                h1_text = h1.get_text() 
                property_types = [
                    'Apartment', 'Duplex', 'Villa', 'Townhouse', 'Twinhouse',
                    'Chalet', 'Penthouse', 'Studio', 'Office', 'Retail',
                    'Cabin', 'Clinic', 'Loft', 'Pharmacy', 'Building',
                    'Administrative', 'Family House'
                ]
                # Check for longest match first (e.g. "Family House" before "House")
                for pt in sorted(property_types, key=len, reverse=True):
                    if pt.lower() in h1_text.lower():
                        details['property_type'] = pt
                        break

        # Priority 3: Fallback to text search (risky, keep as last resort)
        if not details.get('property_type'):
             for pt in ['Studio', 'Chalet', 'Villa', 'Apartment']: # Check specifics first
                if re.search(rf'\b{pt}\b', all_text, re.IGNORECASE):
                    details['property_type'] = pt
                    break
        
        # === Area ===
        # Check prop_data first
        if prop_data.get('min_area'):
             details['area_min'] = int(prop_data.get('min_area'))
        if prop_data.get('max_area'):
             details['area_max'] = int(prop_data.get('max_area'))
             
        if not details.get('area_min'):
            area_match = re.search(r'(\d+)\s*m[²2]\s*[-~]\s*(\d+)\s*m[²2]', all_text)
            if area_match:
                details['area_min'] = int(area_match.group(1))
                details['area_max'] = int(area_match.group(2))
            else:
                single_area = re.search(r'(\d+)\s*m[²2]', all_text)
                if single_area:
                    area = int(single_area.group(1))
                    details['area_min'] = area
                    details['area_max'] = area
        
        # === Bedrooms ===
        # Priority: prop_data -> HTML Regex
        if 'bedrooms' in prop_data:
            details['bedrooms'] = int(prop_data['bedrooms'])
        else:
            # Stricter regex: Look for "Bedrooms" followed closely by number
            # Avoids matching "Reference No 12345 Bedrooms"
            # Matches: "Bedrooms: 3" or "3 Bedrooms"
            beds_match = re.search(r'(?:Bedrooms?|Beds?)\s*[:\-]?\s*(\d+)\b', all_text, re.IGNORECASE)
            if not beds_match:
                 beds_match = re.search(r'(\d+)\s*(?:Bedrooms?|Beds?)\b', all_text, re.IGNORECASE)
            
            if beds_match:
                details['bedrooms'] = int(beds_match.group(1))
        
        # Correction for Studios: They shouldn't have many bedrooms
        if details.get('property_type') == 'Studio' and details.get('bedrooms', 0) > 1:
            details['bedrooms'] = 1
        
        # === Bathrooms ===
        if 'bathrooms' in prop_data:
            details['bathrooms'] = int(prop_data['bathrooms'])
        else:
             baths_match = re.search(r'(?:Bathrooms?|Baths?)\s*[:\-]?\s*(\d+)\b', all_text, re.IGNORECASE)
             if not baths_match:
                  baths_match = re.search(r'(\d+)\s*(?:Bathrooms?|Baths?)\b', all_text, re.IGNORECASE)
                  
             if baths_match:
                details['bathrooms'] = int(baths_match.group(1))
        
        # === Delivery Year ===
        if 'delivery_year' in prop_data:
             details['delivery_year'] = int(prop_data['delivery_year'])
        else:
            delivery_match = re.search(r'Delivery\s*(?:In)?\s*(20\d{2})', all_text, re.IGNORECASE)
            if delivery_match:
                details['delivery_year'] = int(delivery_match.group(1))
        
        # === Compound Name ===
        # ... existing logic for compound ...
        compound_match = re.search(r'Compound\s+([A-Za-z][\w\s\-]+?)(?=Sale|Finishing|$)', all_text, re.IGNORECASE)
        if compound_match:
             details['compound_name'] = compound_match.group(1).strip()
        else:
             compound_data = prop_data.get('compound', {})
             if isinstance(compound_data, dict):
                 details['compound_name'] = compound_data.get('name', '')
        
        # === Sale Type ===
        # ... existing logic ...
        if 'Resale' in all_text:
            details['sale_type'] = 'Resale'
        elif 'Developer Sale' in all_text or 'Developer' in all_text:
            details['sale_type'] = 'Developer Sale'
        elif prop_data.get('sale_type'):
            details['sale_type'] = prop_data.get('sale_type')
        
        # === Finishing ===
        # Check specific values first to avoid partial matching
        # "Semi-Finished" contains "Finished" -> Order matters
        finishing_text = all_text # Or scopes to table if possible
        if 'Semi-Finished' in finishing_text or 'Semi Finished' in finishing_text:
            details['finishing'] = 'Semi-Finished'
        elif 'Not Finished' in finishing_text or 'Unfinished' in finishing_text or 'Core' in finishing_text:
            details['finishing'] = 'Not Finished'
        elif 'Furnished' in finishing_text:
            details['finishing'] = 'Furnished'
        elif 'Finished' in finishing_text:
             details['finishing'] = 'Finished'
        elif prop_data.get('finishing'):
             details['finishing'] = prop_data.get('finishing')
        
        return details
    
    def _get_compound_info(self, compound_name: str) -> Dict:
        """Get compound details from lookup."""
        if not compound_name:
            return {}
        return self.compound_lookup.get(compound_name.lower().strip(), {})
    
    def _extract_amenities(self, soup: BeautifulSoup, prop_data: Dict) -> List[str]:
        """Extract amenities list."""
        amenities = []
        
        # From __NEXT_DATA__
        amenities_data = prop_data.get('amenities', []) or prop_data.get('features', [])
        for am in amenities_data:
            if isinstance(am, dict):
                name = am.get('name', '')
                if name:
                    amenities.append(name)
            elif am:
                amenities.append(str(am))
        
        if amenities:
            return list(set(amenities))[:20]
        
        # From HTML - look for Amenities section
        amenities_section = soup.find(string=re.compile(r'Amenities', re.IGNORECASE))
        if amenities_section:
            parent = amenities_section.find_parent(['div', 'section'])
            if parent:
                # Get all text items that look like amenities
                items = parent.find_all(['span', 'div', 'li'])
                for item in items:
                    text = self.clean_text(item.get_text())
                    if text and text != 'Amenities' and len(text) < 50 and len(text) > 2:
                        amenities.append(text)
        
        return list(set(amenities))[:20]
    
    def _extract_coordinates(self, prop_data: Dict, soup: BeautifulSoup) -> Tuple[Optional[float], Optional[float]]:
        """Extract lat/lng coordinates."""
        lat, lng = None, None
        
        # From __NEXT_DATA__
        lat = prop_data.get('lat') or prop_data.get('latitude')
        lng = prop_data.get('lng') or prop_data.get('longitude')
        
        # Check compound data
        if not lat or not lng:
            compound = prop_data.get('compound', {})
            if isinstance(compound, dict):
                lat = compound.get('lat') or compound.get('latitude')
                lng = compound.get('lng') or compound.get('longitude')
        
        return lat, lng
    
    async def _extract_payment_plans(self, prop_data: Dict) -> List[Dict]:
        """
        Extract payment plans.
        Priority 1: Check prop_data (JSON).
        Priority 2: UI Interaction (Click cards).
        """
        plans = []
        
        # 1. Try JSON data first
        if prop_data:
            json_plans = prop_data.get('payment_plans', []) or prop_data.get('paymentPlans', [])
            if json_plans:
                for jp in json_plans:
                    try:
                        plan = {
                            'name': jp.get('name') or jp.get('title', 'Original Plan'),
                            'total_price': int(jp.get('total_price') or jp.get('price', 0)),
                            'installment_years': int(jp.get('years', 0)),
                            'quarterly_installment': int(jp.get('quarterly', 0)),
                            'total_installments': int(jp.get('total_installments', 0)),
                            'delivery_payment': int(jp.get('delivery_payment', 0)),
                            'maintenance_fees': int(jp.get('maintenance_fees', 0)),
                            'down_payments': []
                        }
                        
                        # Extract down payments
                        dps = jp.get('down_payments', [])
                        for i, dp in enumerate(dps):
                            plan['down_payments'].append({
                                'number': i + 1,
                                'amount': int(dp.get('amount', 0)),
                                'timing': dp.get('timing', '')
                            })
                            
                        plans.append({k: v for k, v in plan.items() if v})
                    except:
                        pass
                
                if plans:
                    return plans
        
        # 2. Fallback to UI Interaction
        try:
            # Find all payment plan cards
            # Selector targets cards with "Original Plan" text
            # We want to click the specific arrow/button div to open the modal
            
            # Locate cards containing "Original Plan"
            plan_cards = await self.page.query_selector_all('div:has-text("Original Plan")')
            
            # Filter to ensure they are the plan cards (checking structure)
            # Usually they are inside a container
            valid_cards = []
            for card in plan_cards:
                # Check if it has an arrow SVG or resembles a card
                if await card.query_selector('svg') or await card.query_selector('[class*="arrow"]'):
                    valid_cards.append(card)
            
            # If no valid cards found, try simpler selector
            if not valid_cards:
                 valid_cards = await self.page.query_selector_all('[class*="PaymentPlanCard"]')
            
            for i, card in enumerate(valid_cards[:5]):
                try:
                    # Scroll into view
                    await card.scroll_into_view_if_needed()
                    await asyncio.sleep(0.5)
                    
                    # Try clicking the arrow specifically
                    arrow = await card.query_selector('svg, [class*="arrow"], [class*="chevron"]')
                    if arrow:
                         await arrow.click()
                    else:
                         # Click the card body (center)
                         box = await card.bounding_box()
                         if box:
                             await self.page.mouse.click(box['x'] + box['width']/2, box['y'] + box['height']/2)
                    
                    # Wait for modal
                    await asyncio.sleep(1.5)
                    
                    # Parse modal content
                    plan = await self._parse_payment_modal()
                    if plan:
                        plans.append(plan)
                    
                    # Close modal
                    await self._close_modal()
                    
                except Exception as e:
                    logger.debug(f"Error clicking/parsing plan {i}: {e}")
                    await self._close_modal()
                    
        except Exception as e:
            logger.debug(f"Error extracting payment plans via UI: {e}")
        
        return plans
    
    async def _parse_payment_modal(self) -> Optional[Dict]:
        """Parse the payment plan modal content."""
        try:
            html = await self.get_page_content()
            soup = self.parse_html(html)
            
            # Look for modal content
            modal = soup.select_one(
                '[class*="modal"], [class*="popup"], [class*="dialog"], '
                '[role="dialog"], [class*="overlay"]'
            )
            
            if not modal:
                return None
            
            # Use separator for get_text to ensure words don't merge
            modal_text = modal.get_text(separator=' ')
            plan = {}
            
            # Plan Name (e.g., "Original Plan")
            name_match = re.search(r'(Original Plan|Escale|Starting From)', modal_text)
            if name_match:
                plan['name'] = name_match.group(1)
            
            # Years
            years_match = re.search(r'(\d+)\s*Years?', modal_text, re.IGNORECASE)
            if years_match:
                plan['installment_years'] = int(years_match.group(1))
            
            # Quarterly installment
            # Handle "68,020 EGP Quarterly" or "Quarterly 68,020 EGP"
            quarterly_match = re.search(r'([\d,]+)\s*EGP\s*(?:Quarterly|quarterly)', modal_text)
            if not quarterly_match:
                quarterly_match = re.search(r'(?:Quarterly|quarterly)\s*(?:Installment)?\s*[:\-]?\s*([\d,]+)\s*EGP', modal_text)
            
            if quarterly_match:
                plan['quarterly_installment'] = int(quarterly_match.group(1).replace(',', ''))
            
            # Total Price
            # Handle "Total Price 2,864,000 EGP" with potential whitespace/separators
            total_match = re.search(r'Total\s*Price\s*[:\-]?\s*([\d,]+)\s*EGP', modal_text, re.IGNORECASE)
            if total_match:
                plan['total_price'] = int(total_match.group(1).replace(',', ''))
            
            # Down Payments
            down_payments = []
            dp_pattern = r'Down\s*Payment\s*(\d)\s*([\d,]+)\s*EGP'
            for match in re.finditer(dp_pattern, modal_text, re.IGNORECASE):
                dp_num = int(match.group(1))
                dp_amount = int(match.group(2).replace(',', ''))
                down_payments.append({'number': dp_num, 'amount': dp_amount})
            
            if down_payments:
                plan['down_payments'] = down_payments
            
            # Total Installments
            installments_match = re.search(r'Total\s*Installments\s*([\d,]+)\s*EGP', modal_text, re.IGNORECASE)
            if installments_match:
                plan['total_installments'] = int(installments_match.group(1).replace(',', ''))
            
            # Delivery Payment
            delivery_match = re.search(r'Delivery\s*Payment\s*([\d,]+)\s*EGP', modal_text, re.IGNORECASE)
            if delivery_match:
                plan['delivery_payment'] = int(delivery_match.group(1).replace(',', ''))
            
            # Maintenance Fees
            maintenance_match = re.search(r'[Mm]aintenance\s*[Ff]ees?\s*([\d,]+)\s*EGP', modal_text)
            if maintenance_match:
                plan['maintenance_fees'] = int(maintenance_match.group(1).replace(',', ''))
            
            return plan if plan else None
            
        except Exception as e:
            logger.debug(f"Error parsing payment modal: {e}")
            return None
    
    async def _close_modal(self):
        """Close any open modal."""
        try:
            close_btns = await self.page.query_selector_all(
                'button[class*="close"], [class*="modal"] button svg, '
                'svg[class*="close"], [aria-label*="close"], [aria-label*="Close"]'
            )
            for btn in close_btns:
                try:
                    await btn.click()
                    return
                except:
                    pass
            
            # Fallback: press Escape
            await self.page.keyboard.press('Escape')
        except:
            pass
    
    def _extract_description(self, soup: BeautifulSoup, prop_data: Dict) -> str:
        """Extract About/description section."""
        # From HTML
        about_header = soup.find(string=re.compile(r'^About\s', re.IGNORECASE))
        if about_header:
            parent = about_header.find_parent(['div', 'section'])
            if parent:
                # Get all text after the header
                texts = []
                for elem in parent.find_all(['p', 'div'], recursive=False):
                    text = self.clean_text(elem.get_text())
                    if text and len(text) > 20:
                        texts.append(text)
                if texts:
                    return DataCleaner.html_to_text(' '.join(texts))[:5000]
        
        # From __NEXT_DATA__
        description = prop_data.get('description', '')
        if description:
            return DataCleaner.html_to_text(description)[:5000]
        
        return ''
    
    def _extract_images(self, prop_data: Dict, soup: BeautifulSoup) -> List[str]:
        """Extract gallery images."""
        images = []
        
        # From __NEXT_DATA__
        for field in ['images', 'gallery', 'photos', 'media']:
            img_data = prop_data.get(field, [])
            if isinstance(img_data, list):
                for img in img_data:
                    url = img.get('url') if isinstance(img, dict) else img
                    if url and url not in images:
                        images.append(url)
        
        # Main image
        main_img = prop_data.get('image') or prop_data.get('main_image')
        if main_img and main_img not in images:
            images.insert(0, main_img)
        
        # From HTML if no images found
        if not images:
            img_tags = soup.select('img[src*="nawy"], img[src*="cloudinary"]')
            for img in img_tags[:10]:
                src = img.get('src') or img.get('data-src')
                if src and 'logo' not in src.lower():
                    if not src.startswith('http'):
                        src = f"https:{src}" if src.startswith('//') else src
                    images.append(src)
        
        return images[:15]


# === PROGRESS MANAGEMENT ===

def load_progress() -> Dict:
    """Load scraping progress from file."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {'last_page': 0, 'scraped_urls': []}


def save_progress(page: int, scraped_urls: List[str]):
    """Save scraping progress to file."""
    with open(PROGRESS_FILE, 'w') as f:
        json.dump({
            'last_page': page,
            'scraped_urls': scraped_urls[-1000:],  # Keep last 1000 URLs
            'updated_at': datetime.now().isoformat()
        }, f, indent=2)


def get_existing_unit_urls() -> Set[str]:
    """Get URLs of units already in MongoDB."""
    urls = set()
    units = db_client._db['units'].find({}, {'nawy_url': 1})
    for unit in units:
        if unit.get('nawy_url'):
            urls.add(unit['nawy_url'])
    return urls


# === MAIN SCRAPING FUNCTION ===

async def scrape_all_units(start_page: int = 1, end_page: int = 1737):
    """Main function to scrape all units."""
    
    console.print(Panel.fit(
        "[bold cyan]NAWY.COM - UNIT SCRAPER v2[/]\n"
        "Comprehensive property data extraction",
        border_style="cyan"
    ))
    
    # Initialize database
    console.print("\nConnecting to MongoDB...")
    db_client.connect()
    
    # Get collection stats
    console.print(f"   Compounds: {db_client._db['compounds'].count_documents({})}")
    console.print(f"   Developers: {db_client._db['developers'].count_documents({})}")
    console.print(f"   Units: {db_client._db['units'].count_documents({})}")
    
    # Load progress
    progress = load_progress()
    existing_urls = get_existing_unit_urls()
    
    console.print(f"\n   Existing units in MongoDB: {len(existing_urls)}")
    console.print(f"   Last completed page: {progress.get('last_page', 0)}")
    
    # Resume from last page if applicable
    if progress.get('last_page', 0) > 0 and start_page == 1:
        start_page = progress['last_page'] + 1
        console.print(f"   [yellow]Resuming from page {start_page}[/]")
    
    console.print(f"\n   Pages to scrape: {start_page} to {end_page}")
    # console.print("\n   Press Enter to start...")
    # input()
    
    # Initialize scraper
    scraper = UnitScraperV2()
    await scraper.initialize()
    scraper.build_compound_lookup()
    
    stats = {
        'total_scraped': 0,
        'total_skipped': 0,
        'total_failed': 0,
        'pages_completed': 0
    }
    
    try:
        for page_num in range(start_page, end_page + 1):
            logger.info(f"📄 Page {page_num}/{end_page}")
            
            # Get unit URLs from this page
            unit_urls = await scraper.get_unit_urls_from_page(page_num)
            logger.info(f"   Found {len(unit_urls)} units on page")
            
            for i, unit_url in enumerate(unit_urls):
                # Skip if already scraped
                if unit_url in existing_urls:
                    stats['total_skipped'] += 1
                    continue
                
                logger.info(f"   [{i+1}/{len(unit_urls)}] Scraping: {unit_url[:60]}...")
                
                # Scrape unit
                unit_data = await scraper.scrape_unit(unit_url)
                
                if unit_data:
                    # Save to MongoDB
                    try:
                        db_client.upsert_unit(unit_data)
                        stats['total_scraped'] += 1
                        existing_urls.add(unit_url)
                        logger.info(f"       ✅ {unit_data.get('name', '')[:50]}")
                    except Exception as e:
                        logger.error(f"       ❌ DB error: {e}")
                        stats['total_failed'] += 1
                else:
                    logger.warning(f"       ❌ Failed to scrape")
                    stats['total_failed'] += 1
            
            # Save progress after each page
            stats['pages_completed'] += 1
            save_progress(page_num, list(existing_urls)[-1000:])
            
            # Stats every 10 pages
            if page_num % 10 == 0:
                console.print(f"\n📊 Progress: Page {page_num}")
                console.print(f"   Scraped: {stats['total_scraped']}")
                console.print(f"   Skipped: {stats['total_skipped']}")
                console.print(f"   Failed: {stats['total_failed']}\n")
    
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Scraping interrupted by user[/]")
    
    finally:
        await scraper.close()
        db_client.disconnect()
    
    console.print("\n" + "="*50)
    console.print("[bold green]✅ Scraping Complete![/]")
    console.print(f"   Total Scraped: {stats['total_scraped']}")
    console.print(f"   Total Skipped: {stats['total_skipped']}")
    console.print(f"   Total Failed: {stats['total_failed']}")
    console.print(f"   Pages Completed: {stats['pages_completed']}")
    
    return stats


# === ENTRY POINT ===

def main():
    parser = argparse.ArgumentParser(description='Nawy Unit Scraper v2')
    parser.add_argument('--start', type=int, default=1, help='Start page number')
    parser.add_argument('--end', type=int, default=1737, help='End page number')
    parser.add_argument('--clear', action='store_true', help='Clear all units before scraping')
    
    args = parser.parse_args()
    
    if args.clear:
        console.print("\n[red]🗑️ Clearing all units from MongoDB...[/]")
        db_client.connect()
        result = db_client._db['units'].delete_many({})
        console.print(f"   Deleted {result.deleted_count} units")
        
        # Also clear progress file
        if os.path.exists(PROGRESS_FILE):
            os.remove(PROGRESS_FILE)
            console.print("   Cleared progress file")
        
        db_client.disconnect()
    
    try:
        asyncio.run(scrape_all_units(args.start, args.end))
    except Exception as e:
        logger.error(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()
