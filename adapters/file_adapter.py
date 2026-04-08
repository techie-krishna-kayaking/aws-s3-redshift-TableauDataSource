"""
File adapter for CSV, JSON, Parquet, and Excel files.
Handles loading and metadata extraction for file-based data sources.
"""
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List
import logging

from .base_adapter import BaseAdapter
from utils.helpers import resolve_path

logger = logging.getLogger(__name__)


class FileAdapter(BaseAdapter):
    """
    Adapter for file-based data sources.
    
    Supports:
    - CSV (.csv)
    - JSON (.json)
    - Parquet (.parquet)
    - Excel (.xlsx, .xls)
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize file adapter.
        
        Args:
            config: Configuration dictionary with keys:
                - path: Path to file (relative or absolute)
                - format: File format (csv, json, parquet, excel) - optional, auto-detected
                - sheet_name: For Excel files, which sheet to read (default: 0)
                - json_orient: For JSON files, orientation (default: 'records')
                - encoding: File encoding for text files (optional, auto-detects common encodings)
                - sep: Delimiter for CSV files (default: ',')
        """
        super().__init__(config)
        self.path = resolve_path(config['path'])
        self.format = config.get('format', self._detect_format())
        self.sheet_name = config.get('sheet_name', 0)
        self.json_orient = config.get('json_orient', 'records')
        self.encoding = config.get('encoding')
        self.sep = config.get('sep', ',')
        
        if not self.path.exists():
            raise FileNotFoundError(f"File not found: {self.path}")
    
    def _detect_format(self) -> str:
        """Detect file format from extension."""
        ext = self.path.suffix.lower()
        
        format_map = {
            '.csv': 'csv',
            '.json': 'json',
            '.parquet': 'parquet',
            '.xlsx': 'excel',
            '.xls': 'excel'
        }
        
        if ext not in format_map:
            raise ValueError(f"Unsupported file extension: {ext}. Supported: {list(format_map.keys())}")
        
        return format_map[ext]
    
    def load(self) -> pd.DataFrame:
        """
        Load data from file.
        
        Returns:
            DataFrame with file contents
        """
        logger.info(f"Loading {self.format} file: {self.path}")
        
        try:
            if self.format == 'csv':
                encodings_to_try = [self.encoding] if self.encoding else ['utf-8', 'utf-16', 'utf-8-sig', 'iso-8859-1', 'cp1252']
                df = None
                last_err = None
                
                for enc in encodings_to_try:
                    try:
                        df = pd.read_csv(
                            self.path,
                            dtype=object,
                            keep_default_na=False,
                            na_values=[''],
                            encoding=enc,
                            sep=self.sep,
                            on_bad_lines='error'
                        )
                        break
                    except (UnicodeDecodeError, UnicodeError, ValueError) as e:
                        # Value error sometimes raised by pandas when parsing engine fails on encoding issues
                        last_err = e
                        continue
                
                if df is None:
                    if last_err:
                        raise last_err
                    raise ValueError(f"Could not read CSV file {self.path} with provided encodings.")
            
            elif self.format == 'json':
                df = pd.read_json(
                    self.path,
                    orient=self.json_orient,
                    dtype=object
                )
            
            elif self.format == 'parquet':
                df = pd.read_parquet(self.path)
                # Convert to object for consistent comparison
                df = df.astype(object)
            
            elif self.format == 'excel':
                df = pd.read_excel(
                    self.path,
                    sheet_name=self.sheet_name,
                    dtype=object,
                    keep_default_na=False,
                    na_values=['']
                )
            
            else:
                raise ValueError(f"Unsupported format: {self.format}")
            
            logger.info(f"Loaded {len(df)} rows, {len(df.columns)} columns")
            
            # Ensure consistent column casing and object type for comparison
            df.columns = df.columns.str.lower()
            self._data = df.astype(object)
            return self._data
        
        except Exception as e:
            logger.error(f"Error loading file {self.path}: {e}")
            raise
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Get metadata about the file.
        
        Returns:
            Dictionary with file metadata
        """
        if self._data is None:
            self._data = self.load()
        
        # Get column types (before conversion to object)
        column_info = []
        for col in self._data.columns:
            column_info.append({
                'name': col,
                'dtype': str(self._data[col].dtype),
                'null_count': int(self._data[col].isna().sum())
            })
        
        return {
            'source_type': 'file',
            'file_format': self.format,
            'source_path': str(self.path),
            'row_count': len(self._data),
            'column_count': len(self._data.columns),
            'columns': column_info,
            'file_size_bytes': self.path.stat().st_size
        }
    
    def __repr__(self) -> str:
        return f"FileAdapter(format={self.format}, path={self.path.name})"
