"""
Adapter package initialization.
Exports all adapter classes for easy importing.
"""
from .base_adapter import BaseAdapter
from .file_adapter import FileAdapter
from .table_adapter import TableAdapter
from .datasource_adapter import DataSourceAdapter

__all__ = [
    'BaseAdapter',
    'FileAdapter',
    'TableAdapter',
    'DataSourceAdapter'
]
