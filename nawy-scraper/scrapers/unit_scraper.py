"""
Unit Scraper for Nawy.com
Scrapes individual units from compound pages.
"""
import asyncio
import re
import logging
from typing import List, Dict, Optional
from datetime import datetime

from .base_scraper import BaseScraper
from config.settings import settings

logger = logging.getLogger(__name__)


class UnitScraper(BaseScraper):
    """
    Scraper for units within compounds.
    Units are typically listed on compound detail pages.
    """
    
    def __init__(self):
        super().__init__()
        self.scraped_units: List[Dict] = []
    
    async def scrape_units_from_compound(
        self, 
        compound_url: str,
        compound_name: str = None,
        compound_id: str = None
    ) -> List[Dict]:
        """
        Scrape all units from a compound page.
        
        Args:
            compound_url: URL of the compound page
            compound_name: Name for reference
            compound_id: MongoDB ID if known
        
        Returns:
            List of unit dictionaries
        """
        await self.initialize()
        
        try:
            if not await self.safe_goto(compound_url):
                return []
            
            await asyncio.sleep(2)
            
            # Scroll to load units (may be lazy loaded)
            await self.scroll_to_bottom(max_scrolls=5)
            
            # Try __NEXT_DATA__ first
            next_data = await self.extract_next_data()
            
            if next_data:
                units = self._extract_units_from_next_data(
                    next_data, compound_name, compound_id
                )
                if units:
                    self.scraped_units.extend(units)
                    return units
            
            # Fallback to HTML
            html = await self.get_page_content()
            units = self._extract_units_from_html(
                html, compound_url, compound_name, compound_id
            )
            self.scraped_units.extend(units)
            
            return units
            
        finally:
            await self.close()
    
    def _extract_units_from_next_data(
        self, 
        next_data: Dict,
        compound_name: str = None,
        compound_id: str = None
    ) -> List[Dict]:
        """Extract units from __NEXT_DATA__."""
        units = []
        
        try:
            page_props = next_data.get('props', {}).get('pageProps', {})
            
            # Try different locations for units data
            units_data = (
                page_props.get('units') or
                page_props.get('compound', {}).get('units') or
                page_props.get('data', {}).get('units') or
                page_props.get('available_units') or
                []
            )
            
            for unit in units_data:
                parsed = self._parse_unit(unit, compound_name, compound_id)
                if parsed:
                    units.append(parsed)
            
            logger.info(f"   Found {len(units)} units from __NEXT_DATA__")
            
        except Exception as e:
            logger.debug(f"Error extracting units: {e}")
        
        return units
    
    def _parse_unit(
        self, 
        unit_data: Dict,
        compound_name: str = None,
        compound_id: str = None
    ) -> Optional[Dict]:
        """Parse a single unit from data."""
        try:
            unit_type = (
                unit_data.get('type') or 
                unit_data.get('unit_type') or 
                unit_data.get('property_type') or
                'apartment'
            )
            
            # Normalize type
            type_mapping = {
                'شقة': 'apartment',
                'فيلا': 'villa',
                'دوبلكس': 'duplex',
                'بنتهاوس': 'penthouse',
                'شاليه': 'chalet',
                'توين هاوس': 'townhouse',
                'تاون هاوس': 'townhouse',
            }
            unit_type = type_mapping.get(unit_type, unit_type)
            
            unit = {
                'nawy_id': str(unit_data.get('id', '')),
                'compound_name': compound_name,
                'compound_id': compound_id,
                'type': unit_type,
                'area': unit_data.get('area') or unit_data.get('size'),
                'price': unit_data.get('price') or unit_data.get('total_price'),
                'price_per_sqm': unit_data.get('price_per_sqm'),
                'bedrooms': unit_data.get('bedrooms') or unit_data.get('beds'),
                'bathrooms': unit_data.get('bathrooms') or unit_data.get('baths'),
                'finishing': unit_data.get('finishing') or unit_data.get('finish_type'),
                'floor_number': unit_data.get('floor') or unit_data.get('floor_number'),
                'view': unit_data.get('view') or unit_data.get('view_type'),
                'delivery_year': unit_data.get('delivery_year'),
                'status': 'Available',  # If listed, assume available
                
                # Payment info
                'down_payment': unit_data.get('down_payment'),
                'down_payment_percent': unit_data.get('down_payment_percent'),
                'installment_years': unit_data.get('installment_years') or unit_data.get('payment_years'),
                'monthly_installment': unit_data.get('monthly_installment'),
                
                # Images
                'images_urls': self._extract_unit_images(unit_data),
                'floor_plan_url': unit_data.get('floor_plan'),
                
                # URL
                'url': unit_data.get('url') or unit_data.get('link'),
                
                'scraped_at': datetime.utcnow().isoformat(),
            }
            
            # Calculate price per sqm if not provided
            if unit['price'] and unit['area'] and not unit['price_per_sqm']:
                unit['price_per_sqm'] = round(unit['price'] / unit['area'], 2)
            
            # Clean None values
            unit = {k: v for k, v in unit.items() if v is not None}
            
            return unit
            
        except Exception as e:
            logger.debug(f"Error parsing unit: {e}")
            return None
    
    def _extract_unit_images(self, unit_data: Dict) -> List[str]:
        """Extract unit images."""
        images = []
        
        for field in ['images', 'photos', 'gallery']:
            img_data = unit_data.get(field, [])
            if isinstance(img_data, list):
                for img in img_data:
                    url = img.get('url') if isinstance(img, dict) else img
                    if url:
                        images.append(url)
        
        main_img = unit_data.get('image') or unit_data.get('main_image')
        if main_img and main_img not in images:
            images.insert(0, main_img)
        
        return images[:5]  # Limit to 5
    
    def _extract_units_from_html(
        self, 
        html: str, 
        compound_url: str,
        compound_name: str = None,
        compound_id: str = None
    ) -> List[Dict]:
        """Extract units from HTML (fallback)."""
        units = []
        soup = self.parse_html(html)
        
        # Find unit cards/items
        unit_cards = soup.select(
            '.unit-card, .property-card, .listing-item, '
            '[class*="unit-"], [class*="property-item"]'
        )
        
        for card in unit_cards:
            unit = self._parse_unit_from_card(card, compound_name, compound_id)
            if unit:
                units.append(unit)
        
        logger.info(f"   Found {len(units)} units from HTML")
        return units
    
    def _parse_unit_from_card(
        self, 
        card, 
        compound_name: str = None,
        compound_id: str = None
    ) -> Optional[Dict]:
        """Parse unit from an HTML card element."""
        try:
            # Type
            unit_type = 'apartment'
            type_elem = card.select_one('.unit-type, .property-type, [class*="type"]')
            if type_elem:
                unit_type = self.clean_text(type_elem.get_text()).lower()
            
            # Area
            area = None
            area_elem = card.select_one('.area, .size, [class*="area"]')
            if area_elem:
                area = self.parse_area(area_elem.get_text())
            
            # Price
            price = None
            price_elem = card.select_one('.price, [class*="price"]')
            if price_elem:
                price = self.parse_price(price_elem.get_text())
            
            # Bedrooms
            bedrooms = None
            beds_elem = card.select_one('.beds, .bedrooms, [class*="bed"]')
            if beds_elem:
                beds_match = re.search(r'(\d+)', beds_elem.get_text())
                if beds_match:
                    bedrooms = int(beds_match.group(1))
            
            # URL
            url = None
            link = card.select_one('a[href]')
            if link:
                url = link.get('href', '')
            
            if not price and not area:
                return None
            
            return {
                'compound_name': compound_name,
                'compound_id': compound_id,
                'type': unit_type,
                'area': area,
                'price': price,
                'bedrooms': bedrooms,
                'url': url,
                'scraped_at': datetime.utcnow().isoformat(),
            }
            
        except:
            return None
    
    async def scrape_units_from_compounds(
        self, 
        compounds: List[Dict],
        max_per_compound: int = None
    ) -> List[Dict]:
        """
        Scrape units from multiple compounds.
        
        Args:
            compounds: List of compound dicts with 'nawy_url' and optionally 'name', '_id'
            max_per_compound: Max units to scrape per compound
        
        Returns:
            All scraped units
        """
        await self.initialize()
        all_units = []
        
        try:
            for i, compound in enumerate(compounds, 1):
                url = compound.get('nawy_url')
                name = compound.get('name')
                _id = str(compound.get('_id', ''))
                
                if not url:
                    continue
                
                logger.info(f"[{i}/{len(compounds)}] Scraping units: {name}")
                
                if not await self.safe_goto(url):
                    continue
                
                await asyncio.sleep(2)
                await self.scroll_to_bottom(max_scrolls=3)
                
                next_data = await self.extract_next_data()
                
                if next_data:
                    units = self._extract_units_from_next_data(next_data, name, _id)
                else:
                    html = await self.get_page_content()
                    units = self._extract_units_from_html(html, url, name, _id)
                
                if max_per_compound:
                    units = units[:max_per_compound]
                
                all_units.extend(units)
                logger.info(f"   ✅ {len(units)} units")
                
                await self.random_delay()
            
            return all_units
            
        finally:
            await self.close()
