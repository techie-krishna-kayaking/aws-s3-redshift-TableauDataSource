"""
DataSource adapter for Tableau TWBX files.
Extracts and compares datasource metadata and column definitions.
"""
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List
import pandas as pd
import logging
from difflib import SequenceMatcher

from .base_adapter import BaseAdapter
from utils.helpers import resolve_path

logger = logging.getLogger(__name__)


class DataSourceAdapter(BaseAdapter):
    """
    Adapter for Tableau TWBX datasource files.
    
    Extracts datasource metadata and column information for comparison.
    Note: This adapter returns metadata as a DataFrame for consistency,
    but the actual comparison logic differs from file/table adapters.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize datasource adapter.
        
        Args:
            config: Configuration dictionary with keys:
                - path: Path to TWBX file
                - datasource_name: Specific datasource to extract (optional, uses first if not specified)
        """
        super().__init__(config)
        self.path = resolve_path(config['path'])
        self.datasource_name = config.get('datasource_name', None)
        
        if not self.path.exists():
            raise FileNotFoundError(f"TWBX file not found: {self.path}")
        
        if self.path.suffix.lower() != '.twbx':
            raise ValueError(f"Expected .twbx file, got: {self.path.suffix}")
        
        self._tree = None
        self._datasources = None
    
    def _extract_twb(self) -> ET.ElementTree:
        """Extract TWB XML from TWBX file."""
        if self._tree is not None:
            return self._tree
        
        logger.info(f"Extracting TWB from: {self.path}")
        
        with zipfile.ZipFile(self.path, 'r') as z:
            twb_files = [f for f in z.namelist() if f.endswith('.twb')]
            
            if not twb_files:
                raise ValueError(f"No .twb file found in {self.path}")
            
            with z.open(twb_files[0]) as f:
                self._tree = ET.parse(f)
        
        return self._tree
    
    def _extract_column_info(self, datasource_element) -> Dict[str, Dict[str, Any]]:
        """Extract column information from a datasource element."""
        columns_info = {}
        
        # Method 1: metadata-records (most common)
        metadata_records = datasource_element.findall('.//metadata-record')
        
        for record in metadata_records:
            local_name = record.find(".//local-name")
            local_type = record.find(".//local-type")
            
            if local_name is not None and local_name.text:
                col_name = local_name.text.strip('[]')
                
                # Skip system columns
                if col_name.startswith('System') or not col_name:
                    continue
                
                datatype = local_type.text if local_type is not None else 'unknown'
                
                columns_info[col_name] = {
                    'raw_name': local_name.text,
                    'datatype': datatype,
                    'source': 'metadata-record'
                }
        
        # Method 2: column elements (fallback)
        if not columns_info:
            columns = datasource_element.findall('.//column')
            
            for col in columns:
                col_name = col.attrib.get('name', col.attrib.get('caption', ''))
                
                if not col_name or col_name.startswith('[System'):
                    continue
                
                clean_name = col_name.strip('[]')
                
                columns_info[clean_name] = {
                    'raw_name': col_name,
                    'caption': col.attrib.get('caption', col_name),
                    'datatype': col.attrib.get('datatype', 'unknown'),
                    'role': col.attrib.get('role', 'unknown'),
                    'type': col.attrib.get('type', 'unknown'),
                    'source': 'column-element'
                }
        
        # Method 3: element search (last resort)
        if not columns_info:
            for elem in datasource_element.iter():
                if 'name' in elem.attrib:
                    name = elem.attrib['name']
                    if name.startswith('[') and not name.startswith('[System'):
                        clean_name = name.strip('[]')
                        if clean_name and clean_name not in columns_info:
                            columns_info[clean_name] = {
                                'raw_name': name,
                                'datatype': elem.attrib.get('datatype', elem.attrib.get('type', 'unknown')),
                                'source': 'element-search'
                            }
        
        return columns_info
    
    def _get_datasources(self) -> Dict[str, Dict[str, Any]]:
        """Get all datasources from the TWBX file."""
        if self._datasources is not None:
            return self._datasources
        
        tree = self._extract_twb()
        root = tree.getroot()
        
        ds_list = root.findall('.//datasource')
        
        # Filter out built-in datasources
        ds_filtered = [
            ds for ds in ds_list 
            if ds.attrib.get('name', '') not in ['Parameters', 'Sample - Superstore']
        ]
        
        self._datasources = {}
        
        for idx, ds in enumerate(ds_filtered):
            ds_name = ds.attrib.get('caption', ds.attrib.get('name', f'Datasource_{idx}'))
            columns_info = self._extract_column_info(ds)
            
            self._datasources[ds_name] = {
                'columns': columns_info,
                'element': ds,
                'caption': ds.attrib.get('caption', ''),
                'name': ds.attrib.get('name', '')
            }
            
            logger.info(f"Found datasource '{ds_name}' with {len(columns_info)} columns")
        
        return self._datasources
    
    def load(self) -> pd.DataFrame:
        """
        Load datasource metadata as DataFrame.
        
        Returns:
            DataFrame with columns: datasource_name, column_name, datatype
        """
        datasources = self._get_datasources()
        
        # Convert to DataFrame format
        rows = []
        for ds_name, ds_info in datasources.items():
            for col_name, col_info in ds_info['columns'].items():
                rows.append({
                    'datasource_name': ds_name,
                    'column_name': col_name,
                    'datatype': col_info.get('datatype', 'unknown'),
                    'raw_name': col_info.get('raw_name', col_name)
                })
        
        df = pd.DataFrame(rows)
        
        logger.info(f"Loaded {len(datasources)} datasources with {len(df)} total columns")
        
        df.columns = df.columns.str.lower()
        self._data = df.astype(object)
        return self._data
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Get metadata about the TWBX file.
        
        Returns:
            Dictionary with TWBX metadata
        """
        datasources = self._get_datasources()
        
        # Get workbook metadata
        tree = self._extract_twb()
        root = tree.getroot()
        
        return {
            'source_type': 'datasource',
            'file_format': 'twbx',
            'source_path': str(self.path),
            'workbook_name': root.attrib.get('name', 'Unknown'),
            'datasource_count': len(datasources),
            'datasources': list(datasources.keys()),
            'worksheet_count': len(root.findall('.//worksheet')),
            'dashboard_count': len(root.findall('.//dashboard')),
            'file_size_bytes': self.path.stat().st_size
        }
    
    def get_datasource_columns(self, datasource_name: str = None) -> Dict[str, Dict[str, Any]]:
        """
        Get columns for a specific datasource.
        
        Args:
            datasource_name: Name of datasource (uses first if None)
        
        Returns:
            Dictionary of column info
        """
        datasources = self._get_datasources()
        
        if not datasources:
            return {}
        
        if datasource_name is None:
            # Return first datasource
            datasource_name = list(datasources.keys())[0]
        
        if datasource_name not in datasources:
            # Try fuzzy matching
            best_match = self._find_matching_datasource(datasource_name, list(datasources.keys()))
            if best_match:
                logger.warning(f"Datasource '{datasource_name}' not found, using '{best_match}'")
                datasource_name = best_match
            else:
                raise ValueError(f"Datasource '{datasource_name}' not found")
        
        return datasources[datasource_name]['columns']
    
    def _find_matching_datasource(self, name: str, datasource_list: List[str]) -> str:
        """Find matching datasource by similarity."""
        best_match = None
        best_ratio = 0
        
        for ds in datasource_list:
            ratio = SequenceMatcher(None, name.lower(), ds.lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = ds
        
        # Return match if similarity > 50%
        return best_match if best_ratio > 0.5 else None
    
    def __repr__(self) -> str:
        return f"DataSourceAdapter(path={self.path.name})"
