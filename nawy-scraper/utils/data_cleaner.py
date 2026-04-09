"""
Data Cleaning and Normalization Utilities
"""
import re
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class DataCleaner:
    """
    Utilities for cleaning and normalizing scraped data.
    """
    
    # Arabic to English numeral mapping
    ARABIC_NUMERALS = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
    
    # Location normalization mapping
    LOCATION_MAPPING = {
        'التجمع الخامس': 'New Cairo',
        'القاهرة الجديدة': 'New Cairo',
        'العاصمة الإدارية': 'New Administrative Capital',
        'العاصمة الадминистративية الجديدة': 'New Administrative Capital',
        '6 أكتوبر': '6th of October',
        'السادس من أكتوبر': '6th of October',
        'الساحل الشمالي': 'North Coast',
        'العين السخنة': 'Ain Sokhna',
        'مستقبل سيتي': 'Mostakbal City',
        'مدينة المستقبل': 'Mostakbal City',
        'الشروق': 'El Shorouk',
        'بدر': 'Badr City',
        'هليوبوليس الجديدة': 'New Heliopolis',
        'الجونة': 'El Gouna',
        'شرم الشيخ': 'Sharm El Sheikh',
        'الغردقة': 'Hurghada',
    }
    
    # Unit type normalization
    UNIT_TYPE_MAPPING = {
        'شقة': 'apartment',
        'فيلا': 'villa',
        'apartment': 'apartment',
        'villa': 'villa',
        'duplex': 'duplex',
        'دوبلكس': 'duplex',
        'penthouse': 'penthouse',
        'بنتهاوس': 'penthouse',
        'townhouse': 'townhouse',
        'تاون هاوس': 'townhouse',
        'توين هاوس': 'twin_house',
        'twin house': 'twin_house',
        'chalet': 'chalet',
        'شاليه': 'chalet',
        'studio': 'studio',
        'استوديو': 'studio',
        'office': 'office',
        'مكتب': 'office',
    }
    
    # Finishing type normalization
    FINISHING_MAPPING = {
        'fully finished': 'fully_finished',
        'تشطيب كامل': 'fully_finished',
        'semi finished': 'semi_finished',
        'نصف تشطيب': 'semi_finished',
        'core & shell': 'core_shell',
        'core shell': 'core_shell',
        'على الطوب': 'core_shell',
        'not finished': 'core_shell',
        'super lux': 'super_lux',
        'سوبر لوكس': 'super_lux',
        'lux': 'lux',
        'لوكس': 'lux',
    }
    
    @classmethod
    def html_to_text(cls, html: str) -> str:
        """Convert HTML to plain text by stripping all tags."""
        if not html:
            return ""
        
        # Remove script and style elements
        text = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Replace <br>, <p>, <div>, <li> with newlines
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</?(p|div|h[1-6]|li|ul|ol)\s*[^>]*>', '\n', text, flags=re.IGNORECASE)
        
        # Remove all remaining HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Decode HTML entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        text = text.replace('&#39;', "'")
        
        # Clean up multiple newlines and spaces
        text = re.sub(r'\n\s*\n+', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        
        # Strip and trim
        text = '\n'.join(line.strip() for line in text.split('\n'))
        text = text.strip()
        
        return text
    
    @classmethod
    def clean_text(cls, text: str) -> str:
        """Clean and normalize text."""
        if not text:
            return ""
        
        # Convert Arabic numerals
        text = text.translate(cls.ARABIC_NUMERALS)
        
        # Normalize whitespace
        text = ' '.join(text.strip().split())
        
        return text
    
    @classmethod
    def parse_price(cls, price_text: str) -> Optional[float]:
        """Parse price from text (handles Arabic and English)."""
        if not price_text:
            return None
        
        # Clean and convert
        text = cls.clean_text(price_text)
        
        # Remove currency and units
        text = re.sub(r'(جنيه|EGP|ج\.م|LE|مليون|million|ألف|thousand)', '', text, flags=re.IGNORECASE)
        
        # Extract numbers
        numbers = re.findall(r'[\d,.]+', text)
        
        if not numbers:
            return None
        
        try:
            # Take the first number, remove commas
            price_str = numbers[0].replace(',', '')
            price = float(price_str)
            
            # Handle "million" / "مليون"
            if 'مليون' in price_text.lower() or 'million' in price_text.lower():
                price *= 1_000_000
            elif 'ألف' in price_text.lower() or 'thousand' in price_text.lower():
                price *= 1_000
            
            return price
            
        except (ValueError, TypeError):
            return None
    
    @classmethod
    def parse_area(cls, area_text: str) -> Optional[float]:
        """Parse area (sqm) from text."""
        if not area_text:
            return None
        
        text = cls.clean_text(area_text)
        
        # Remove units
        text = re.sub(r'(متر|sqm|m²|م²|sq\.m)', '', text, flags=re.IGNORECASE)
        
        # Extract number
        numbers = re.findall(r'[\d,.]+', text)
        
        if not numbers:
            return None
        
        try:
            return float(numbers[0].replace(',', ''))
        except:
            return None
    
    @classmethod
    def normalize_location(cls, location: str) -> str:
        """Normalize location name to English."""
        if not location:
            return ""
        
        location = cls.clean_text(location)
        
        # Check mapping
        for arabic, english in cls.LOCATION_MAPPING.items():
            if arabic in location:
                return english
        
        return location
    
    @classmethod
    def normalize_unit_type(cls, unit_type: str) -> str:
        """Normalize unit type to standard format."""
        if not unit_type:
            return "apartment"
        
        key = cls.clean_text(unit_type).lower()
        
        return cls.UNIT_TYPE_MAPPING.get(key, key)
    
    @classmethod
    def normalize_finishing(cls, finishing: str) -> str:
        """Normalize finishing type."""
        if not finishing:
            return ""
        
        key = cls.clean_text(finishing).lower()
        
        return cls.FINISHING_MAPPING.get(key, key)
    
    @classmethod
    def extract_bedrooms(cls, text: str) -> Optional[int]:
        """Extract number of bedrooms from text."""
        if not text:
            return None
        
        text = cls.clean_text(text)
        
        # Common patterns
        patterns = [
            r'(\d+)\s*(غرف|غرفة|bedroom|bed|br)',
            r'(\d+)\s*BR',
            r'(\d+)\+\d',  # e.g., "3+1"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        
        # Just a number
        numbers = re.findall(r'\d+', text)
        if numbers:
            num = int(numbers[0])
            if 0 <= num <= 10:  # Reasonable bedroom count
                return num
        
        return None
    
    @classmethod
    def clean_compound(cls, compound: Dict) -> Dict:
        """Clean and normalize a compound record."""
        cleaned = compound.copy()
        
        # Clean text fields
        if cleaned.get('name'):
            cleaned['name'] = cls.clean_text(cleaned['name'])
        
        if cleaned.get('description'):
            # Convert HTML to plain text
            cleaned['description'] = cls.html_to_text(cleaned['description'])[:5000]
        
        # Normalize location
        if cleaned.get('location'):
            cleaned['location'] = cls.normalize_location(cleaned['location'])
        
        # Clean prices
        if isinstance(cleaned.get('price_min'), str):
            cleaned['price_min'] = cls.parse_price(cleaned['price_min'])
        if isinstance(cleaned.get('price_max'), str):
            cleaned['price_max'] = cls.parse_price(cleaned['price_max'])
        
        # Ensure price_min <= price_max
        if cleaned.get('price_min') and cleaned.get('price_max'):
            if cleaned['price_min'] > cleaned['price_max']:
                cleaned['price_min'], cleaned['price_max'] = cleaned['price_max'], cleaned['price_min']
        
        # Clean developer name
        if cleaned.get('developer_name'):
            cleaned['developer_name'] = cls.clean_text(cleaned['developer_name'])
        
        # Ensure lists
        if not isinstance(cleaned.get('images_urls'), list):
            cleaned['images_urls'] = []
        if not isinstance(cleaned.get('amenities_list'), list):
            cleaned['amenities_list'] = []
        
        # Remove empty string values
        cleaned = {k: v for k, v in cleaned.items() if v != ''}
        
        return cleaned
    
    @classmethod
    def clean_unit(cls, unit: Dict) -> Dict:
        """Clean and normalize a unit record."""
        cleaned = unit.copy()
        
        # Normalize type
        if cleaned.get('type'):
            cleaned['type'] = cls.normalize_unit_type(cleaned['type'])
        
        # Parse area
        if isinstance(cleaned.get('area'), str):
            cleaned['area'] = cls.parse_area(cleaned['area'])
        
        # Parse price
        if isinstance(cleaned.get('price'), str):
            cleaned['price'] = cls.parse_price(cleaned['price'])
        
        # Calculate price per sqm
        if cleaned.get('price') and cleaned.get('area') and not cleaned.get('price_per_sqm'):
            cleaned['price_per_sqm'] = round(cleaned['price'] / cleaned['area'], 2)
        
        # Normalize finishing
        if cleaned.get('finishing'):
            cleaned['finishing'] = cls.normalize_finishing(cleaned['finishing'])
        
        # Extract bedrooms if needed
        if not cleaned.get('bedrooms') and cleaned.get('type'):
            cleaned['bedrooms'] = cls.extract_bedrooms(cleaned.get('description', ''))
        
        return cleaned
    
    @classmethod
    def clean_developer(cls, developer: Dict) -> Dict:
        """Clean and normalize a developer record."""
        cleaned = developer.copy()
        
        if cleaned.get('dev_name'):
            cleaned['dev_name'] = cls.clean_text(cleaned['dev_name'])
        
        if cleaned.get('description'):
            cleaned['description'] = cls.clean_text(cleaned['description'])[:2000]
        
        return cleaned
    
    @classmethod
    def deduplicate_by_name(cls, items: List[Dict], key: str = 'name') -> List[Dict]:
        """Remove duplicates based on a key field."""
        seen = set()
        unique = []
        
        for item in items:
            name = item.get(key, '').lower().strip()
            if name and name not in seen:
                seen.add(name)
                unique.append(item)
        
        return unique
    
    @classmethod
    def merge_records(cls, existing: Dict, new: Dict) -> Dict:
        """Merge new data into existing record, preferring non-null new values."""
        merged = existing.copy()
        
        for key, value in new.items():
            # Skip None/empty values in new data
            if value is None or value == '' or value == []:
                continue
            
            # Update if existing is None/empty or if new value is "better"
            existing_value = merged.get(key)
            
            if existing_value is None or existing_value == '' or existing_value == []:
                merged[key] = value
            elif isinstance(value, list) and isinstance(existing_value, list):
                # Merge lists
                merged[key] = list(set(existing_value + value))
            elif key in ('scraped_at', 'updated_at'):
                # Always use newer timestamp
                merged[key] = value
        
        return merged
