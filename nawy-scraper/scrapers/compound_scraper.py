"""
Compound Scraper for Nawy.com
Scrapes compound listings and detail pages.
"""
import asyncio
import re
import os
import json
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
from urllib.parse import urljoin, urlparse

from .base_scraper import BaseScraper
from config.settings import settings
from database.models import CompoundModel, Amenities

logger = logging.getLogger(__name__)

# Progress file path
PROGRESS_FILE = "scraping_progress.json"


class CompoundScraper(BaseScraper):
    """
    Scraper for Nawy.com compounds.
    
    Workflow:
    1. Scrape compound listings (paginated)
    2. For each compound, scrape detail page
    3. Extract: name, location, developer, amenities, prices, units, images
    
    Features:
    - Progress saving: saves checkpoint after each page/compound
    - Resume capability: can resume from last checkpoint if interrupted
    """
    
    def __init__(self):
        super().__init__()
        self.compounds_list_url = settings.compounds_url
        self.scraped_compounds: List[Dict] = []
        self.progress_file = PROGRESS_FILE
    
    def _save_progress(self, data: Dict):
        """Save progress to checkpoint file."""
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            logger.debug(f"💾 Progress saved to {self.progress_file}")
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
    
    def _clear_progress(self):
        """Clear progress file after successful completion."""
        try:
            if os.path.exists(self.progress_file):
                os.remove(self.progress_file)
                logger.info(f"🗑️ Cleared progress file")
        except Exception as e:
            logger.error(f"Failed to clear progress: {e}")
    
    async def scrape_all_compounds(
        self, 
        max_pages: int = None, 
        max_compounds: int = None,
        resume: bool = True
    ) -> List[Dict]:
        """
        Main method to scrape all compounds.
        
        Args:
            max_pages: Limit number of listing pages (None = all 128)
            max_compounds: Limit total compounds (None = all)
            resume: If True, resume from last checkpoint
        
        Returns:
            List of compound data dictionaries
        """
        await self.initialize()
        
        # Try to resume from checkpoint
        compound_urls = []
        start_index = 0
        
        if resume:
            progress = self._load_progress()
            if progress:
                compound_urls = progress.get('compound_urls', [])
                # Only use last_scraped_index - compounds are saved directly to MongoDB
                start_index = progress.get('last_scraped_index', 0)
                logger.info(f"▶️ Resuming: {len(compound_urls)} URLs, starting at index {start_index}")
        
        try:
            # Step 1: Get compound URLs if not already loaded
            if not compound_urls:
                logger.info("📋 Step 1: Scraping compound listings...")
                compound_urls = await self._scrape_listing_pages(max_pages)
                
                # Save URLs immediately
                self._save_progress({
                    'compound_urls': compound_urls,
                    'last_scraped_index': 0,
                    'timestamp': datetime.utcnow().isoformat()
                })
            
            if max_compounds:
                compound_urls = compound_urls[:max_compounds]
            
            logger.info(f"✅ Found {len(compound_urls)} compounds, starting from index {start_index}")
            
            # Step 2: Scrape each compound detail page
            logger.info("📊 Step 2: Scraping compound details...")
            
            for i in range(start_index, len(compound_urls)):
                url = compound_urls[i]
                logger.info(f"[{i+1}/{len(compound_urls)}] Scraping: {url}")
                
                compound_data = await self._scrape_compound_detail(url)
                
                if compound_data:
                    self.scraped_compounds.append(compound_data)
                    logger.info(f"   ✅ {compound_data.get('name', 'Unknown')}")
                    
                    # Save to MongoDB immediately (real-time updates)
                    try:
                        from database.connection import db_client
                        if db_client._db is not None:
                            db_client.upsert_compound(compound_data)
                    except Exception as e:
                        logger.debug(f"   ⚠️ MongoDB save deferred: {e}")
                else:
                    logger.warning(f"   ❌ Failed to scrape")
                
                # Save progress after each compound (only track index, not data)
                self._save_progress({
                    'compound_urls': compound_urls,
                    'last_scraped_index': i + 1,
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                # Random delay between compounds
                await self.random_delay()
            
            logger.info(f"\n🎉 Scraping complete! {len(self.scraped_compounds)} compounds scraped")
            
            # Clear progress file on successful completion
            self._clear_progress()
            
            return self.scraped_compounds
            
        except KeyboardInterrupt:
            logger.warning(f"\n⚠️ Interrupted! Progress saved at index {i if 'i' in dir() else start_index}. Resume with --resume flag")
            raise
        except Exception as e:
            logger.error(f"Error during scraping: {e}. Progress saved.")
            raise
        finally:
            await self.close()
    
    async def _scrape_listing_pages(self, max_pages: int = None) -> List[str]:
        """Scrape compound listing pages using page_number pagination."""
        compound_urls = []
        current_page = 1
        max_page_number = max_pages or 128  # 128 total pages on Nawy
        
        logger.info(f"📄 Scraping {max_page_number} pages of compounds...")
        
        while current_page <= max_page_number:
            # Build page URL with page_number parameter
            url = f"{self.compounds_list_url}?page_number={current_page}"
            
            # Navigate to page
            if not await self.safe_goto(url):
                logger.warning(f"Failed to load page {current_page}")
                current_page += 1
                continue
            
            # Wait for content to load
            await asyncio.sleep(1.5)
            
            # Scroll to ensure all content is visible
            await self.human_scroll(300)
            await asyncio.sleep(0.5)
            
            # Extract compound URLs from HTML
            html = await self.get_page_content()
            urls = self._extract_urls_from_html(html)
            
            if urls:
                compound_urls.extend(urls)
                # Log progress every 5 pages
                if current_page % 5 == 0 or current_page == 1:
                    logger.info(f"   Page {current_page}/{max_page_number}: Found {len(urls)} compounds (Total: {len(compound_urls)})")
            else:
                logger.warning(f"   Page {current_page}: No compounds found")
            
            current_page += 1
            
            # Random delay between pages to avoid rate limiting
            await self.random_delay()
        
        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in compound_urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        
        logger.info(f"✅ Found {len(unique_urls)} unique compound URLs from {max_page_number} pages")
        return unique_urls



    
    def _extract_urls_from_next_data(self, next_data: Dict) -> List[str]:
        """Extract compound URLs from Next.js data."""
        urls = []
        
        try:
            # Navigate through the data structure
            # Common patterns: props.pageProps.compounds, props.pageProps.data.compounds
            page_props = next_data.get('props', {}).get('pageProps', {})
            
            # Try different possible locations
            compounds = (
                page_props.get('compounds') or 
                page_props.get('data', {}).get('compounds') or
                page_props.get('initialData', {}).get('compounds') or
                []
            )
            
            for compound in compounds:
                slug = compound.get('slug') or compound.get('url_slug')
                compound_id = compound.get('id')
                
                if slug:
                    url = f"{settings.base_url}/ar/compound/{compound_id}-{slug}" if compound_id else f"{settings.base_url}/ar/compound/{slug}"
                    urls.append(url)
            
        except Exception as e:
            logger.debug(f"Error parsing __NEXT_DATA__: {e}")
        
        return urls
    
    def _extract_urls_from_html(self, html: str) -> List[str]:
        """Extract compound URLs from HTML content."""
        urls = []
        soup = self.parse_html(html)
        
        # Find compound links (adjust selectors based on actual site structure)
        link_patterns = [
            'a[href*="/ar/compound/"]',
            'a[href*="/compound/"]',
        ]
        
        for pattern in link_patterns:
            links = soup.select(pattern)
            for link in links:
                href = link.get('href', '')
                if href:
                    full_url = urljoin(settings.base_url, href)
                    if '/compound/' in full_url and full_url not in urls:
                        urls.append(full_url)
        
        return urls
    
    async def _has_next_page(self) -> bool:
        """Check if there's a next page in pagination."""
        try:
            # Look for pagination controls
            next_button = await self.page.query_selector(
                'a[aria-label="Next"], button[aria-label="Next"], '
                '.pagination-next:not([disabled]), '
                'a:has-text("التالي"), button:has-text("التالي")'
            )
            
            if next_button:
                is_disabled = await next_button.get_attribute('disabled')
                return not is_disabled
            
            return False
        except:
            return False
    
    async def _scrape_compound_detail(self, url: str) -> Optional[Dict]:
        """Scrape a single compound detail page."""
        if not await self.safe_goto(url):
            return None
        
        # Wait for content
        await asyncio.sleep(2)
        await self.human_scroll(400)
        
        # Try __NEXT_DATA__ first (most reliable)
        next_data = await self.extract_next_data()
        
        if next_data:
            compound = self._parse_compound_from_next_data(next_data, url)
            if compound:
                return compound
        
        # Fall back to HTML parsing
        html = await self.get_page_content()
        return self._parse_compound_from_html(html, url)
    
    def _parse_compound_from_next_data(self, next_data: Dict, url: str) -> Optional[Dict]:
        """Parse compound data from Next.js __NEXT_DATA__."""
        try:
            page_props = next_data.get('props', {}).get('pageProps', {})
            
            # The compound data might be at different locations
            compound_data = (
                page_props.get('compound') or
                page_props.get('data', {}).get('compound') or
                page_props.get('initialData', {}).get('compound') or
                page_props
            )
            
            if not compound_data or not isinstance(compound_data, dict):
                return None
            
            # Extract ID from URL if not in data
            nawy_id = str(compound_data.get('id', ''))
            if not nawy_id:
                url_match = re.search(r'/compound/(\d+)', url)
                if url_match:
                    nawy_id = url_match.group(1)
            
            # Build compound model
            compound = {
                'name': compound_data.get('name') or compound_data.get('title', ''),
                'nawy_id': nawy_id,
                'nawy_slug': compound_data.get('slug') or compound_data.get('url_slug', ''),
                'nawy_url': url,
                'description': compound_data.get('description', ''),
                'location': self._extract_location(compound_data),
                
                # Developer
                'developer_name': self._extract_developer_name(compound_data),
                
                # Coordinates
                'lat': compound_data.get('lat') or compound_data.get('latitude'),
                'lng': compound_data.get('lng') or compound_data.get('longitude'),
                
                # Prices
                'price_min': compound_data.get('min_price') or compound_data.get('price_from'),
                'price_max': compound_data.get('max_price') or compound_data.get('price_to'),
                
                # Units
                'unit_count': compound_data.get('units_count') or compound_data.get('total_units'),
                'available_units': compound_data.get('available_units_count'),
                
                # Images
                'images_urls': self._extract_images(compound_data),
                
                # Amenities
                'amenities_list': self._extract_amenities_list(compound_data),
                
                # Status
                'project_status': compound_data.get('status') or compound_data.get('project_status'),
                'project_type': compound_data.get('type') or compound_data.get('project_type'),
                'delivery_year': compound_data.get('delivery_year'),
                
                # Metadata
                'scraped_at': datetime.utcnow().isoformat(),
            }
            
            # Clean up None values
            compound = {k: v for k, v in compound.items() if v is not None}
            
            return compound
            
        except Exception as e:
            logger.error(f"Error parsing __NEXT_DATA__: {e}")
            return None
    
    def _extract_location(self, data: Dict) -> str:
        """Extract location from compound data."""
        # Try different location field names
        location_fields = ['location', 'area', 'city', 'district', 'neighborhood', 'area_name', 'location_name']
        
        for field in location_fields:
            value = data.get(field)
            if value:
                if isinstance(value, dict):
                    name = value.get('name') or value.get('area_name') or value.get('title', '')
                    if name:
                        return name
                elif isinstance(value, str) and value.strip():
                    return value.strip()
        
        # Try deeper nested structures
        for key in ['compound', 'project', 'property']:
            nested = data.get(key, {})
            if isinstance(nested, dict):
                for field in location_fields:
                    value = nested.get(field)
                    if value:
                        if isinstance(value, dict):
                            name = value.get('name', '')
                            if name:
                                return name
                        elif isinstance(value, str) and value.strip():
                            return value.strip()
        
        return ''
    
    def _extract_developer_name(self, data: Dict) -> str:
        """Extract developer name from compound data."""
        # Try direct developer fields
        developer_fields = ['developer', 'developer_info', 'developer_data', 'dev']
        
        for field in developer_fields:
            developer = data.get(field)
            if developer:
                if isinstance(developer, dict):
                    name = developer.get('name') or developer.get('dev_name') or developer.get('title', '')
                    if name:
                        return name
                elif isinstance(developer, str) and developer.strip():
                    return developer.strip()
        
        # Try direct developer_name field
        if data.get('developer_name'):
            return data.get('developer_name')
        
        # Try deeper nested structures
        for key in ['compound', 'project', 'property']:
            nested = data.get(key, {})
            if isinstance(nested, dict):
                for field in developer_fields:
                    developer = nested.get(field)
                    if developer:
                        if isinstance(developer, dict):
                            name = developer.get('name', '')
                            if name:
                                return name
                        elif isinstance(developer, str) and developer.strip():
                            return developer.strip()
        
        return ''
    
    def _extract_images(self, data: Dict) -> List[str]:
        """Extract image URLs from compound data."""
        images = []
        
        # Try different image field names
        image_fields = ['images', 'gallery', 'photos', 'media']
        
        for field in image_fields:
            img_data = data.get(field, [])
            
            if isinstance(img_data, list):
                for img in img_data:
                    if isinstance(img, str):
                        images.append(img)
                    elif isinstance(img, dict):
                        url = img.get('url') or img.get('src') or img.get('image')
                        if url:
                            images.append(url)
        
        # Main image
        main_image = data.get('image') or data.get('main_image') or data.get('cover_image')
        if main_image and main_image not in images:
            images.insert(0, main_image)
        
        return images[:20]  # Limit to 20 images
    
    def _extract_amenities_list(self, data: Dict) -> List[str]:
        """Extract amenities as a simple list."""
        amenities = []
        
        # Try different amenity field names
        amenity_fields = ['amenities', 'features', 'facilities']
        
        for field in amenity_fields:
            amenity_data = data.get(field, [])
            
            if isinstance(amenity_data, list):
                for item in amenity_data:
                    if isinstance(item, str):
                        amenities.append(item)
                    elif isinstance(item, dict):
                        name = item.get('name') or item.get('title') or item.get('label')
                        if name:
                            amenities.append(name)
        
        return list(set(amenities))  # Remove duplicates
    
    def _parse_compound_from_html(self, html: str, url: str) -> Optional[Dict]:
        """Parse compound data from HTML content (fallback method)."""
        try:
            soup = self.parse_html(html)
            
            # Extract compound name from page title or heading
            name = ''
            title_elem = soup.select_one('h1, .compound-title, .project-name')
            if title_elem:
                name = self.clean_text(title_elem.get_text())
            
            if not name:
                # Try meta title
                meta_title = soup.select_one('meta[property="og:title"]')
                if meta_title:
                    name = meta_title.get('content', '').split('|')[0].strip()
            
            if not name:
                return None
            
            # Extract ID from URL
            nawy_id = ''
            url_match = re.search(r'/compound/(\d+)', url)
            if url_match:
                nawy_id = url_match.group(1)
            
            # Extract location
            location = ''
            location_elem = soup.select_one('.location, .area-name, [class*="location"]')
            if location_elem:
                location = self.clean_text(location_elem.get_text())
            
            # Extract developer
            developer = ''
            dev_elem = soup.select_one('.developer-name, .developer, [class*="developer"]')
            if dev_elem:
                developer = self.clean_text(dev_elem.get_text())
            
            # Extract prices
            price_min = None
            price_max = None
            price_elem = soup.select_one('.price, .price-range, [class*="price"]')
            if price_elem:
                price_text = price_elem.get_text()
                prices = re.findall(r'[\d,]+', price_text)
                if len(prices) >= 2:
                    price_min = self.parse_price(prices[0])
                    price_max = self.parse_price(prices[1])
                elif len(prices) == 1:
                    price_min = self.parse_price(prices[0])
            
            # Extract images
            images = []
            img_elems = soup.select('img[src*="compound"], img[src*="project"], .gallery img')
            for img in img_elems[:10]:
                src = img.get('src') or img.get('data-src')
                if src and 'placeholder' not in src.lower():
                    images.append(urljoin(settings.base_url, src))
            
            # Extract amenities
            amenities = []
            amenity_elems = soup.select('.amenity, .feature, [class*="amenity"] li, [class*="feature"] li')
            for elem in amenity_elems:
                text = self.clean_text(elem.get_text())
                if text:
                    amenities.append(text)
            
            # Extract description
            description = ''
            desc_elem = soup.select_one('.description, .about, [class*="description"]')
            if desc_elem:
                description = self.clean_text(desc_elem.get_text())[:1000]  # Limit
            
            compound = {
                'name': name,
                'nawy_id': nawy_id,
                'nawy_url': url,
                'location': location,
                'developer_name': developer,
                'description': description,
                'price_min': price_min,
                'price_max': price_max,
                'images_urls': images,
                'amenities_list': amenities,
                'scraped_at': datetime.utcnow().isoformat(),
            }
            
            # Clean up None values
            compound = {k: v for k, v in compound.items() if v is not None}
            
            return compound
            
        except Exception as e:
            logger.error(f"Error parsing HTML: {e}")
            return None
    
    async def scrape_single_compound(self, url: str) -> Optional[Dict]:
        """Scrape a single compound by URL (useful for testing)."""
        await self.initialize()
        
        try:
            return await self._scrape_compound_detail(url)
        finally:
            await self.close()
