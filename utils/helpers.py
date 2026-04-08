"""
Utility helper functions for the universal data validator.
Provides common functions for data comparison, type coercion, and path resolution.
"""
import pandas as pd
import numpy as np
import re
import os
from pathlib import Path
from typing import List, Tuple, Any, Optional
from dotenv import load_dotenv


def load_environment():
    """Load environment variables from .env file."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=str(env_path))
    return os.environ


def resolve_path(path: str, base_dir: Optional[Path] = None) -> Path:
    """
    Resolve a path (relative or absolute) from the project root.
    
    Args:
        path: Path string (relative or absolute)
        base_dir: Base directory to resolve from (defaults to project root)
    
    Returns:
        Resolved absolute Path object
    """
    path_obj = Path(path)
    
    # If already absolute and exists, return it
    if path_obj.is_absolute():
        return path_obj
    
    # Determine base directory
    if base_dir is None:
        # Use project root (parent of universal-validator)
        base_dir = Path(__file__).parent.parent
    
    # Resolve relative to base directory
    resolved = (base_dir / path_obj).resolve()
    
    return resolved


def parse_primary_keys(pk_string: str) -> List[str]:
    """
    Parse primary key string into list of column names.
    Supports comma, semicolon, and pipe separators.
    
    Args:
        pk_string: String like "id,user_id" or "id;user_id" or "id|user_id"
    
    Returns:
        List of column names
    
    Examples:
        >>> parse_primary_keys("id,user_id")
        ['id', 'user_id']
        >>> parse_primary_keys("id; user_id | status")
        ['id', 'user_id', 'status']
    """
    if not pk_string:
        return []
    
    s = str(pk_string).strip()
    if not s:
        return []
    
    # Split by comma, semicolon, or pipe
    parts = re.split(r'\s*[;,|]\s*', s)
    return [p.strip() for p in parts if p.strip()]


def coerce_to_compare(value: Any) -> Any:
    """
    Normalize a value for comparison by handling type coercion.
    
    Handles:
    - NaN/None → np.nan
    - Bytes → string
    - Numeric strings → int/float
    - Empty strings → ''
    
    Args:
        value: Any value to normalize
    
    Returns:
        Normalized value suitable for comparison
    """
    # Handle NaN/None
    if pd.isna(value):
        return np.nan
    
    # Handle bytes
    if isinstance(value, (bytes, bytearray)):
        try:
            value = value.decode()
        except Exception:
            value = str(value)
    
    # Handle strings
    if isinstance(value, str):
        s = value.strip()
        
        # Empty string
        if s == '':
            return ''
        
        # Try to convert to int
        if re.fullmatch(r'[+-]?\d+', s):
            try:
                return int(s)
            except Exception:
                pass
        
        # Try to convert to float
        if re.fullmatch(r'[+-]?\d+\.\d*', s):
            try:
                return float(s)
            except Exception:
                pass
        
        return s
    
    return value


def compare_values(a: Any, b: Any) -> bool:
    """
    Compare two values with type coercion and NaN handling.
    
    Args:
        a: First value
        b: Second value
    
    Returns:
        True if values are considered equal, False otherwise
    
    Examples:
        >>> compare_values("123", 123)
        True
        >>> compare_values(np.nan, None)
        True
        >>> compare_values("hello", "hello")
        True
    """
    a_norm = coerce_to_compare(a)
    b_norm = coerce_to_compare(b)
    
    # Both NaN
    if pd.isna(a_norm) and pd.isna(b_norm):
        return True
    
    # Try direct comparison
    try:
        return a_norm == b_norm
    except Exception:
        # Fallback to string comparison
        return str(a_norm) == str(b_norm)


def format_pk_values(pk_values: Tuple, pk_cols: List[str]) -> str:
    """
    Format primary key values for display.
    
    Args:
        pk_values: Tuple of primary key values
        pk_cols: List of primary key column names
    
    Returns:
        Formatted string like "id=123, user_id='abc'"
    
    Examples:
        >>> format_pk_values((123, 'abc'), ['id', 'user_id'])
        "id=123, user_id='abc'"
    """
    if not pk_cols:
        return ""
    
    pairs = [f"{col}={repr(val)}" for col, val in zip(pk_cols, pk_values)]
    return ", ".join(pairs)


def get_common_columns(df1: pd.DataFrame, df2: pd.DataFrame) -> List[str]:
    """
    Get list of common columns between two DataFrames.
    
    Args:
        df1: First DataFrame
        df2: Second DataFrame
    
    Returns:
        Sorted list of common column names
    """
    return sorted(set(df1.columns).intersection(set(df2.columns)))


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize a DataFrame for comparison.
    - Convert all columns to object dtype
    - Strip whitespace from string columns
    - Handle NaN values consistently
    
    Args:
        df: DataFrame to normalize
    
    Returns:
        Normalized DataFrame
    """
    df_normalized = df.copy()
    
    # Convert to object dtype
    df_normalized = df_normalized.astype(object)
    
    # Strip whitespace from string columns
    for col in df_normalized.columns:
        if df_normalized[col].dtype == object:
            df_normalized[col] = df_normalized[col].apply(
                lambda x: x.strip() if isinstance(x, str) else x
            )
    
    return df_normalized


def truncate_string(s: str, max_length: int = 100) -> str:
    """
    Truncate a string to max_length with ellipsis.
    
    Args:
        s: String to truncate
        max_length: Maximum length
    
    Returns:
        Truncated string
    """
    if len(s) <= max_length:
        return s
    return s[:max_length-3] + "..."


def safe_repr(value: Any, max_length: int = 100) -> str:
    """
    Safe representation of a value for display.
    
    Args:
        value: Value to represent
        max_length: Maximum length of output
    
    Returns:
        String representation
    """
    try:
        r = repr(value)
        return truncate_string(r, max_length)
    except Exception:
        return truncate_string(str(value), max_length)


def are_types_compatible(type1: str, type2: str) -> bool:
    """
    Check if two data types are "close enough" according to user requirements.
    
    Compatible sets:
    - Numeric: int, float, decimal, number
    - String/Object: object, string, str, text
    - Date/Time: datetime, timestamp, date
    
    Args:
        type1: First type string
        type2: Second type string
    
    Returns:
        True if types are compatible, False otherwise
    """
    t1 = str(type1).lower()
    t2 = str(type2).lower()
    
    if t1 == t2:
        return True
    
    # Numeric compatibility
    numeric_types = {'int', 'float', 'decimal', 'number', 'int64', 'float64', 'numeric'}
    if t1 in numeric_types and t2 in numeric_types:
        return True
        
    # String compatibility (including objects which pandas often uses for strings)
    string_types = {'object', 'string', 'str', 'text', 'varchar', 'char'}
    if t1 in string_types and t2 in string_types:
        return True
        
    # Date compatibility
    date_types = {'datetime', 'timestamp', 'date', 'datetime64[ns]'}
    if t1 in date_types and t2 in date_types:
        return True
        
    return False
