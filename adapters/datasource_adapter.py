"""
DataSource adapter for Tableau TWBX files.
Extracts and compares datasource metadata and actual data from embedded extracts.
"""
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import pandas as pd
import logging
from difflib import SequenceMatcher
import tempfile
import json
import io

from .base_adapter import BaseAdapter
from utils.helpers import resolve_path

logger = logging.getLogger(__name__)

# Try to import hyper library for reading Tableau Hyper files
try:
    import hyper
    HYPER_AVAILABLE = True
except ImportError:
    HYPER_AVAILABLE = False


class DataSourceAdapter(BaseAdapter):
    """
    Adapter for Tableau TWBX datasource files.
    
    Extracts both actual data and metadata from TWBX files:
    - Attempts to extract actual data from embedded files (.hyper, .tde, .csv)
    - Falls back to metadata extraction if no embedded data found
    - Enables full data validation (null checks, duplicates, data comparison)
    
    Supported data sources:
    1. Hyper files (.hyper) - Tableau 2020.1+ native format (requires 'hyper' package)
    2. TDE files (.tde) - Older Tableau Data Extract format
    3. Embedded CSV files (.csv, .tsv, .txt)
    4. Metadata-only mode - schema/column information
    
    The adapter returns data as a DataFrame for consistency with other adapters.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize datasource adapter.
        
        Args:
            config: Configuration dictionary with keys:
                - path: Path to TWBX file
                - datasource_name: Specific datasource to extract (optional, uses first if not specified)
                - extract_data: Whether to extract actual data (default: True)
        """
        super().__init__(config)
        self.path = resolve_path(config['path'])
        self.datasource_name = config.get('datasource_name', None)
        self.extract_data = config.get('extract_data', True)
        
        if not self.path.exists():
            raise FileNotFoundError(f"TWBX file not found: {self.path}")
        
        if self.path.suffix.lower() != '.twbx':
            raise ValueError(f"Expected .twbx file, got: {self.path.suffix}")
        
        self._tree = None
        self._datasources = None
        self._embedded_data = None
        self._data_source_type = None
    
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
    
    def _list_twbx_contents(self) -> List[str]:
        """List all files in TWBX archive."""
        with zipfile.ZipFile(self.path, 'r') as z:
            return z.namelist()
    
    def _extract_hyper_data(self) -> Optional[pd.DataFrame]:
        """
        Extract data from embedded .hyper file (Tableau 2020.1+).
        
        Returns:
            DataFrame if hyper file found and readable, None otherwise
        """
        if not HYPER_AVAILABLE:
            logger.debug("hyper library not installed, skipping .hyper extraction")
            return None
        
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                with zipfile.ZipFile(self.path, 'r') as z:
                    hyper_files = [f for f in z.namelist() if f.endswith('.hyper')]
                    
                    if not hyper_files:
                        return None
                    
                    hyper_file = hyper_files[0]
                    extract_path = Path(tmpdir) / hyper_file.split('/')[-1]
                    
                    with z.open(hyper_file) as f_in:
                        with open(extract_path, 'wb') as f_out:
                            f_out.write(f_in.read())
                    
                    logger.info(f"Extracting data from hyper file: {hyper_file}")
                    
                    # Use hyper library to read the file
                    with hyper.open_database(str(extract_path)) as database:
                        # Get the first table
                        table_names = database.get_table_names()
                        if not table_names:
                            return None
                        
                        table_name = table_names[0]
                        table = database.get_table(table_name)
                        
                        # Read table data into pandas DataFrame
                        rows = []
                        for row in table.rows():
                            rows.append(dict(zip([col.name for col in table.columns], row)))
                        
                        if rows:
                            df = pd.DataFrame(rows)
                            logger.info(f"Loaded {len(df)} rows from hyper file")
                            self._data_source_type = 'hyper'
                            return df
        
        except Exception as e:
            logger.warning(f"Failed to extract hyper data: {e}")
        
        return None
    
    def _extract_tde_data(self) -> Optional[pd.DataFrame]:
        """
        Extract data from embedded .tde file (older Tableau Data Extract).
        
        Returns:
            DataFrame if tde file found and readable, None otherwise
        """
        # TDE format is proprietary and difficult to read without Tableau's libraries
        # This is a placeholder for future enhancement
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                with zipfile.ZipFile(self.path, 'r') as z:
                    tde_files = [f for f in z.namelist() if f.endswith('.tde')]
                    
                    if not tde_files:
                        return None
                    
                    logger.warning(f"TDE files found ({len(tde_files)}), but TDE extraction not yet implemented. "
                                  "Consider using Hyper format or extracting data as CSV first.")
        
        except Exception as e:
            logger.debug(f"Error checking for TDE files: {e}")
        
        return None
    
    def _extract_csv_data(self) -> Optional[pd.DataFrame]:
        """
        Extract data from embedded CSV file in datasource.
        
        Returns:
            DataFrame if CSV data found, None otherwise
        """
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                with zipfile.ZipFile(self.path, 'r') as z:
                    # Look for embedded data in datasources or root
                    csv_files = [f for f in z.namelist() if f.endswith(('.csv', '.tsv', '.txt'))]
                    
                    if not csv_files:
                        return None
                    
                    # Try to load the first CSV file
                    csv_file = csv_files[0]
                    logger.info(f"Extracting data from CSV file: {csv_file}")
                    
                    with z.open(csv_file) as f:
                        # Try to read as CSV with different delimiters
                        try:
                            df = pd.read_csv(f)
                        except:
                            f.seek(0)
                            df = pd.read_csv(f, delimiter='\t')
                    
                    logger.info(f"Loaded {len(df)} rows from CSV file")
                    self._data_source_type = 'csv'
                    return df
        
        except Exception as e:
            logger.debug(f"Failed to extract CSV data: {e}")
        
        return None
    
    def _extract_data_from_twbx(self) -> Optional[pd.DataFrame]:
        """
        Attempt to extract actual data from TWBX file in this order:
        1. Hyper files (.hyper)
        2. TDE files (.tde)
        3. Embedded CSV files
        
        Returns:
            DataFrame with actual data if found, None otherwise
        """
        if not self.extract_data:
            return None
        
        # Try hyper first
        df = self._extract_hyper_data()
        if df is not None:
            return df
        
        # Try TDE
        df = self._extract_tde_data()
        if df is not None:
            return df
        
        # Try CSV
        df = self._extract_csv_data()
        if df is not None:
            return df
        
        return None
    
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
        Load datasource data as DataFrame.
        
        Attempts to extract actual data from embedded files (hyper, tde, csv).
        Falls back to metadata-based extraction if no actual data is available.
        
        Returns:
            DataFrame with data rows (if available) or metadata schema
        """
        # Try to extract actual data first
        if self.extract_data:
            data_df = self._extract_data_from_twbx()
            if data_df is not None:
                logger.info(f"Successfully extracted actual data: {len(data_df)} rows, {len(data_df.columns)} columns")
                data_df.columns = data_df.columns.str.lower()
                self._data = data_df.astype(object)
                return self._data
        
        # Fall back to metadata extraction
        logger.info("No embedded data found, falling back to metadata extraction")
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
        
        logger.info(f"Loaded {len(datasources)} datasources with {len(df)} total columns (metadata)")
        
        df.columns = df.columns.str.lower()
        self._data = df.astype(object)
        return self._data
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Get metadata about the TWBX file and loaded data.
        
        Returns:
            Dictionary with TWBX metadata including:
            - source_type: Type of data source
            - file_format: TWBX format
            - source_path: Path to TWBX file
            - workbook_name: Workbook name
            - datasource_count: Number of datasources
            - has_embedded_data: Whether actual data was loaded
            - data_source_type: Type of embedded data (hyper, csv, metadata, etc.)
            - row_count: Row count if data loaded
            - column_count: Column count if data loaded
        """
        datasources = self._get_datasources()
        
        # Get workbook metadata
        tree = self._extract_twb()
        root = tree.getroot()
        
        # Check if we loaded actual data
        has_actual_data = self._data is not None and self._data_source_type is not None
        
        metadata = {
            'source_type': 'datasource',
            'file_format': 'twbx',
            'source_path': str(self.path),
            'workbook_name': root.attrib.get('name', 'Unknown'),
            'datasource_count': len(datasources),
            'datasources': list(datasources.keys()),
            'worksheet_count': len(root.findall('.//worksheet')),
            'dashboard_count': len(root.findall('.//dashboard')),
            'file_size_bytes': self.path.stat().st_size,
            'has_embedded_data': has_actual_data,
            'data_source_type': self._data_source_type or 'metadata'
        }
        
        # Add row/column counts if data is loaded
        if self._data is not None:
            metadata['row_count'] = len(self._data)
            metadata['column_count'] = len(self._data.columns)
        
        return metadata
    
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
    
    def has_embedded_data(self) -> bool:
        """
        Check if TWBX contains embedded data (hyper, tde, csv).
        
        Returns:
            True if TWBX has embedded data files, False otherwise
        """
        try:
            contents = self._list_twbx_contents()
            has_hyper = any(f.endswith('.hyper') for f in contents)
            has_tde = any(f.endswith('.tde') for f in contents)
            has_csv = any(f.endswith(('.csv', '.tsv', '.txt')) for f in contents)
            return has_hyper or has_tde or has_csv
        except Exception as e:
            logger.debug(f"Error checking for embedded data: {e}")
            return False
    
    def get_data_source_info(self) -> Dict[str, Any]:
        """
        Get detailed information about data sources in TWBX.
        
        Returns:
            Dictionary with information about embedded data availability
        """
        return {
            'has_embedded_data': self.has_embedded_data(),
            'data_loaded_from': self._data_source_type or 'not loaded yet',
            'row_count': len(self._data) if self._data is not None else None,
            'column_count': len(self._data.columns) if self._data is not None else None
        }
    
    def __repr__(self) -> str:
        data_info = f", data_type={self._data_source_type}" if self._data_source_type else ""
        return f"DataSourceAdapter(path={self.path.name}{data_info})"
