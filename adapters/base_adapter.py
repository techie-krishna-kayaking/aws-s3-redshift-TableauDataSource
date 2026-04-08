"""
Base adapter interface for all data sources.
All adapters must implement this interface to ensure consistency.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any
import pandas as pd


class BaseAdapter(ABC):
    """
    Abstract base class for all data source adapters.
    
    All adapters must implement:
    - load(): Load data and return as pandas DataFrame
    - get_metadata(): Return metadata about the data source
    - get_columns(): Return list of column names
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize adapter with configuration.
        
        Args:
            config: Configuration dictionary containing adapter-specific settings
        """
        self.config = config
        self._data = None
        self._metadata = None
    
    @abstractmethod
    def load(self) -> pd.DataFrame:
        """
        Load data from the source and return as pandas DataFrame.
        
        Returns:
            DataFrame with all data from the source
        
        Raises:
            Exception: If data cannot be loaded
        """
        pass
    
    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """
        Get metadata about the data source.
        
        Returns:
            Dictionary containing metadata like:
            - row_count: Number of rows
            - column_count: Number of columns
            - columns: List of column names with types
            - source_type: Type of data source
            - source_path: Path or identifier of source
        """
        pass
    
    def get_columns(self) -> List[str]:
        """
        Get list of column names.
        
        Returns:
            List of column names
        """
        if self._data is None:
            self._data = self.load()
        return list(self._data.columns)
    
    def get_data(self) -> pd.DataFrame:
        """
        Get the loaded data (caches result).
        
        Returns:
            DataFrame with loaded data
        """
        if self._data is None:
            self._data = self.load()
        return self._data
    
    def __repr__(self) -> str:
        """String representation of the adapter."""
        return f"{self.__class__.__name__}({self.config})"
