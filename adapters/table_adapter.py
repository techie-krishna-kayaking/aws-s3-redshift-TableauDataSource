"""
Table adapter for Redshift database tables.
Handles connection, querying, and metadata extraction.
Supports multi-environment configuration.
"""
import pandas as pd
import redshift_connector
from typing import Dict, Any, List, Optional
import logging
import os

from .base_adapter import BaseAdapter
from utils.helpers import load_environment
from utils.env_config import get_environment_config, list_available_environments

logger = logging.getLogger(__name__)


class TableAdapter(BaseAdapter):
    """
    Adapter for Redshift database tables.
    
    Connects to Redshift and loads table data as DataFrame.
    
    Supports two configuration modes:
    1. Environment-based: Specify 'environment' to use predefined credentials
    2. Direct: Specify host, database, user, password directly
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize table adapter.
        
        Args:
            config: Configuration dictionary with keys:
                
                Environment-based mode:
                - environment: Environment name (e.g., 'DEV', 'PREPROD', 'PROD', 'DEV_REVOPS')
                - schema: Database schema name (optional, from env)
                - table: Table name
                
                Direct mode:
                - schema: Database schema name
                - table: Table name
                - host: Redshift host (optional, from env)
                - database: Database name (optional, from env)
                - user: Username (optional, from env)
                - password: Password (optional, from env)
                - port: Port number (optional, from env, default: 5439)
                
                Common:
                - columns: List of specific columns to load (optional, loads all if not specified)
        """
        super().__init__(config)
        
        # Load environment variables
        env = load_environment()
        
        # Check if using environment-based configuration
        if 'environment' in config:
            env_name = config['environment']
            logger.info(f"Using environment-based configuration: {env_name}")
            
            try:
                env_config = get_environment_config(env_name, env)
                
                # Use environment config
                self.host = env_config['host']
                self.database = env_config['database']
                self.user = env_config['user']
                self.password = env_config['password']
                self.port = env_config['port']
                self.schema = config.get('schema', env_config['schema'])
                self.environment = env_name
                
            except ValueError as e:
                # List available environments for helpful error message
                available = list_available_environments(env)
                raise ValueError(
                    f"Error loading environment '{env_name}': {e}\n"
                    f"Available environments: {available}\n"
                    f"Make sure .env file has {env_name}_JDBC_URL, {env_name}_USER, etc."
                )
        else:
            # Direct configuration mode (legacy)
            logger.info("Using direct configuration mode")
            
            self.host = config.get('host', env.get('REDSHIFT_HOST'))
            self.database = config.get('database', env.get('REDSHIFT_DB'))
            self.user = config.get('user', env.get('REDSHIFT_USER'))
            self.password = config.get('password', env.get('REDSHIFT_PASSWORD'))
            self.port = int(config.get('port', env.get('REDSHIFT_PORT', 5439)))
            self.schema = config.get('schema', env.get('REDSHIFT_SCHEMA', 'public'))
            self.environment = None
        
        # Table parameters
        self.table = config['table']
        self.columns = config.get('columns', None)
        
        # Validate required parameters
        if not all([self.host, self.database, self.user]):
            raise ValueError(
                "Missing Redshift credentials. Either:\n"
                "1. Specify 'environment' in config (e.g., environment: DEV)\n"
                "2. Provide host, database, user via config or environment variables"
            )

    
    def _get_connection(self):
        """Create and return a Redshift connection."""
        logger.info(f"Connecting to Redshift: {self.host}:{self.port}/{self.database}")
        
        return redshift_connector.connect(
            host=self.host,
            database=self.database,
            user=self.user,
            password=self.password,
            port=self.port
        )
    
    def _get_table_columns(self, conn) -> List[str]:
        """
        Get list of columns in the table.
        Try information_schema first, then fallback to SELECT * LIMIT 0 (for views).
        """
        # Method 1: information_schema (standard, but might miss late-binding views)
        sql = """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """
        
        try:
            with conn.cursor() as cur:
                cur.execute(sql, [self.schema, self.table])
                columns = [row[0] for row in cur.fetchall()]
                
            if columns:
                return columns
                
            # Method 2: Fallback for Views / Late-binding views (LIMIT 0)
            logger.info(f"Metadata lookup empty for {self.schema}.{self.table}, trying LIMIT 0 query...")
            with conn.cursor() as cur:
                # Use quoted identifiers to handle case sensitivity and special chars
                cur.execute(f'SELECT * FROM "{self.schema}"."{self.table}" LIMIT 0')
                if cur.description:
                    return [desc[0] for desc in cur.description]
            
            return []
            
        except Exception as e:
            logger.warning(f"Error getting columns for {self.schema}.{self.table}: {e}")
            return []
    
    def load(self, pk_columns: Optional[List[str]] = None, pk_values: Optional[List[tuple]] = None) -> pd.DataFrame:
        """
        Load data from Redshift table with optional PK-based filtering.
        
        Args:
            pk_columns: List of primary key column names for WHERE clause filtering (optional)
            pk_values: List of tuples of PK values to filter by (optional)
                       If provided, only rows matching these PK values are loaded
        
        Returns:
            DataFrame with table contents
        """
        conn = self._get_connection()
        
        try:
            # Get table columns
            all_columns = self._get_table_columns(conn)
            
            if not all_columns:
                raise ValueError(f"Table {self.schema}.{self.table} not found or has no columns")
            
            # Determine which columns to select
            if self.columns:
                # Filter to only columns that exist in both config and table
                select_cols = [c for c in all_columns if c in self.columns]
                if not select_cols:
                    logger.warning(f"No matching columns found. Config: {self.columns}, Table: {all_columns}")
                    return pd.DataFrame(dtype=object)
            else:
                select_cols = all_columns
            
            # Build SQL query
            cols_sql = ", ".join([f'"{c}"' for c in select_cols])
            sql = f'SELECT {cols_sql} FROM "{self.schema}"."{self.table}"'
            
            # Add WHERE clause for PK filtering if provided
            if pk_columns and pk_values:
                where_clause = self._build_pk_where_clause(pk_columns, pk_values)
                if where_clause:
                    sql += f' WHERE {where_clause}'
                    logger.info(f"Loading table: {self.schema}.{self.table} ({len(select_cols)} columns) with PK filter ({len(pk_values)} rows)")
                else:
                    logger.info(f"Loading table: {self.schema}.{self.table} ({len(select_cols)} columns)")
            else:
                logger.info(f"Loading table: {self.schema}.{self.table} ({len(select_cols)} columns)")
            
            # Execute query
            df = pd.read_sql(sql, conn)
            
            logger.info(f"Loaded {len(df)} rows from Redshift")
            
            # Ensure consistent column casing and object type for comparison
            df.columns = df.columns.str.lower()
            self._data = df.astype(object)
            return self._data
        
        except Exception as e:
            logger.error(f"Error loading table {self.schema}.{self.table}: {e}")
            raise
        
        finally:
            conn.close()
    
    def _build_pk_where_clause(self, pk_columns: List[str], pk_values: List[tuple]) -> Optional[str]:
        """
        Build a WHERE clause for PK filtering.
        
        Args:
            pk_columns: List of primary key column names
            pk_values: List of tuples of PK values
        
        Returns:
            WHERE clause string or None if no values
        """
        if not pk_values:
            return None
        
        # Normalize column names to lowercase
        pk_cols_lower = [col.lower() for col in pk_columns]
        
        # For single PK: WHERE pk_col IN (val1, val2, ...)
        if len(pk_columns) == 1:
            col = pk_columns[0]
            # Build value list, escaping single quotes
            val_strs = []
            for val_tuple in pk_values:
                val = val_tuple[0] if isinstance(val_tuple, tuple) else val_tuple
                # Safe escaping: replace single quotes with two single quotes
                val_str = str(val).replace("'", "''")
                val_strs.append(f"'{val_str}'")
            
            if len(val_strs) <= 1000:  # Keep under typical SQL IN limit
                vals_sql = ", ".join(val_strs)
                return f'"{col}" IN ({vals_sql})'
            else:
                # For very large PK lists, use UNION of smaller IN clauses
                logger.warning(f"Large PK filter ({len(val_strs)} values) - may impact performance")
                chunks = [val_strs[i:i+1000] for i in range(0, len(val_strs), 1000)]
                conditions = [f'"{col}" IN ({", ".join(chunk)})' for chunk in chunks]
                return f'({" OR ".join(conditions)})'
        
        # For composite PK: WHERE (pk_col1, pk_col2) IN ((val1, val2), ...)
        else:
            cols_sql = ", ".join([f'"{col}"' for col in pk_columns])
            # Build value tuples list
            val_tuples = []
            for val_tuple in pk_values:
                val_strs = [str(v).replace("'", "''") for v in val_tuple]
                quoted_vals = ", ".join([f"'{v}'" for v in val_strs])
                val_tuples.append(f"({quoted_vals})")
            
            if len(val_tuples) <= 500:  # Keep under typical limit for composite keys
                vals_sql = ", ".join(val_tuples)
                return f'({cols_sql}) IN ({vals_sql})'
            else:
                logger.warning(f"Large composite PK filter ({len(val_tuples)} values) - may impact performance")
                # Fall back to chunking
                chunks = [val_tuples[i:i+500] for i in range(0, len(val_tuples), 500)]
                conditions = [f'({cols_sql}) IN ({", ".join(chunk)})' for chunk in chunks]
                return f'({" OR ".join(conditions)})'
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Get metadata about the table.
        
        Returns:
            Dictionary with table metadata
        """
        if self._data is None:
            self._data = self.load()
        
        # Get column info
        column_info = []
        for col in self._data.columns:
            column_info.append({
                'name': col,
                'dtype': str(self._data[col].dtype),
                'null_count': int(self._data[col].isna().sum())
            })
        
        return {
            'source_type': 'table',
            'database': self.database,
            'schema': self.schema,
            'table': self.table,
            'source_path': f"{self.schema}.{self.table}",
            'row_count': len(self._data),
            'column_count': len(self._data.columns),
            'columns': column_info
        }
    
    def __repr__(self) -> str:
        if self.environment:
            return f"TableAdapter(env={self.environment}, schema={self.schema}, table={self.table})"
        return f"TableAdapter(schema={self.schema}, table={self.table})"

