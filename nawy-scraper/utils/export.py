"""
Export utilities for JSON and CSV output.
"""
import os
import json
import csv
import logging
from typing import List, Dict, Any
from datetime import datetime
import pandas as pd

from config.settings import settings

logger = logging.getLogger(__name__)


class Exporter:
    """
    Export scraped data to various formats.
    """
    
    def __init__(self, export_dir: str = None):
        self.export_dir = export_dir or settings.export_dir
        os.makedirs(self.export_dir, exist_ok=True)
    
    def _get_timestamp(self) -> str:
        """Get timestamp string for filenames."""
        return datetime.now().strftime('%Y%m%d_%H%M%S')
    
    def _get_filepath(self, name: str, extension: str) -> str:
        """Get full filepath with timestamp."""
        timestamp = self._get_timestamp()
        filename = f"{name}_{timestamp}.{extension}"
        return os.path.join(self.export_dir, filename)
    
    def to_json(
        self, 
        data: List[Dict], 
        name: str = "export",
        pretty: bool = True
    ) -> str:
        """
        Export data to JSON file.
        
        Args:
            data: List of dictionaries to export
            name: Base filename
            pretty: If True, format with indentation
        
        Returns:
            Path to exported file
        """
        filepath = self._get_filepath(name, 'json')
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(
                data, 
                f, 
                ensure_ascii=False, 
                indent=2 if pretty else None,
                default=str  # Handle datetime and other non-serializable types
            )
        
        logger.info(f"💾 Exported {len(data)} records to: {filepath}")
        return filepath
    
    def to_csv(
        self, 
        data: List[Dict], 
        name: str = "export",
        flatten: bool = True
    ) -> str:
        """
        Export data to CSV file.
        
        Args:
            data: List of dictionaries to export
            name: Base filename
            flatten: If True, flatten nested structures
        
        Returns:
            Path to exported file
        """
        if not data:
            logger.warning("No data to export")
            return ""
        
        filepath = self._get_filepath(name, 'csv')
        
        # Convert to DataFrame for better handling
        df = pd.DataFrame(data)
        
        if flatten:
            df = self._flatten_dataframe(df)
        
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        
        logger.info(f"💾 Exported {len(data)} records to: {filepath}")
        return filepath
    
    def _flatten_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Flatten nested columns in DataFrame."""
        for col in df.columns:
            # Convert lists to comma-separated strings
            if df[col].apply(lambda x: isinstance(x, list)).any():
                df[col] = df[col].apply(
                    lambda x: ', '.join(map(str, x)) if isinstance(x, list) else x
                )
            
            # Convert dicts to JSON strings
            if df[col].apply(lambda x: isinstance(x, dict)).any():
                df[col] = df[col].apply(
                    lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, dict) else x
                )
        
        return df
    
    def to_excel(
        self, 
        data: List[Dict], 
        name: str = "export"
    ) -> str:
        """
        Export data to Excel file.
        
        Args:
            data: List of dictionaries to export
            name: Base filename
        
        Returns:
            Path to exported file
        """
        if not data:
            logger.warning("No data to export")
            return ""
        
        filepath = self._get_filepath(name, 'xlsx')
        
        df = pd.DataFrame(data)
        df = self._flatten_dataframe(df)
        
        df.to_excel(filepath, index=False, engine='openpyxl')
        
        logger.info(f"💾 Exported {len(data)} records to: {filepath}")
        return filepath
    
    def export_all(
        self, 
        compounds: List[Dict] = None,
        developers: List[Dict] = None,
        units: List[Dict] = None,
        format: str = 'both'
    ) -> Dict[str, str]:
        """
        Export all data types at once.
        
        Args:
            compounds: List of compound records
            developers: List of developer records
            units: List of unit records
            format: 'json', 'csv', or 'both'
        
        Returns:
            Dict mapping data type to file paths
        """
        paths = {}
        
        datasets = {
            'compounds': compounds or [],
            'developers': developers or [],
            'units': units or [],
        }
        
        for name, data in datasets.items():
            if not data:
                continue
            
            if format in ('json', 'both'):
                paths[f"{name}_json"] = self.to_json(data, name)
            
            if format in ('csv', 'both'):
                paths[f"{name}_csv"] = self.to_csv(data, name)
        
        return paths
    
    def create_summary_report(
        self,
        compounds: List[Dict] = None,
        developers: List[Dict] = None,
        units: List[Dict] = None
    ) -> str:
        """
        Create a summary report of scraped data.
        
        Returns:
            Path to report file
        """
        report = {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'total_compounds': len(compounds) if compounds else 0,
                'total_developers': len(developers) if developers else 0,
                'total_units': len(units) if units else 0,
            },
            'compounds_by_location': {},
            'developers_by_projects': {},
            'units_by_type': {},
            'price_ranges': {
                'compounds': {},
                'units': {}
            }
        }
        
        # Analyze compounds
        if compounds:
            for c in compounds:
                loc = c.get('location', 'Unknown')
                report['compounds_by_location'][loc] = report['compounds_by_location'].get(loc, 0) + 1
            
            prices = [c.get('price_min') for c in compounds if c.get('price_min')]
            if prices:
                report['price_ranges']['compounds'] = {
                    'min': min(prices),
                    'max': max(prices),
                    'avg': sum(prices) / len(prices)
                }
        
        # Analyze developers
        if developers:
            for d in developers:
                count = d.get('compounds_count', 0) or d.get('total_projects', 0)
                bracket = '0' if count == 0 else ('1-5' if count <= 5 else ('6-10' if count <= 10 else '10+'))
                report['developers_by_projects'][bracket] = report['developers_by_projects'].get(bracket, 0) + 1
        
        # Analyze units
        if units:
            for u in units:
                unit_type = u.get('type', 'unknown')
                report['units_by_type'][unit_type] = report['units_by_type'].get(unit_type, 0) + 1
            
            prices = [u.get('price') for u in units if u.get('price')]
            if prices:
                report['price_ranges']['units'] = {
                    'min': min(prices),
                    'max': max(prices),
                    'avg': sum(prices) / len(prices)
                }
        
        filepath = self._get_filepath('summary_report', 'json')
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"📊 Summary report saved: {filepath}")
        return filepath
