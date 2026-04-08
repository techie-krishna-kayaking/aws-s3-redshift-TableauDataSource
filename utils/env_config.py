"""
Environment configuration helper for multi-environment Redshift support.
Parses JDBC URLs and manages environment-based credentials.
"""
import os
import re
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def parse_jdbc_url(jdbc_url: str) -> Dict[str, Any]:
    """
    Parse JDBC URL into connection parameters.
    
    Format: jdbc:redshift://host:port/database
    
    Args:
        jdbc_url: JDBC connection string
    
    Returns:
        Dictionary with host, port, database
    
    Examples:
        >>> parse_jdbc_url("jdbc:redshift://localhost:54391/ib-dl-it")
        {'host': 'localhost', 'port': 54391, 'database': 'ib-dl-it'}
    """
    # Pattern: jdbc:redshift://host:port/database
    pattern = r'jdbc:redshift://([^:]+):(\d+)/(.+)'
    match = re.match(pattern, jdbc_url)
    
    if not match:
        raise ValueError(f"Invalid JDBC URL format: {jdbc_url}")
    
    host, port, database = match.groups()
    
    return {
        'host': host,
        'port': int(port),
        'database': database
    }


def get_environment_config(env_name: str, env_vars: Dict[str, str] = None) -> Dict[str, Any]:
    """
    Get Redshift configuration for a specific environment.
    
    Looks for environment variables in format:
    - {ENV_NAME}_JDBC_URL
    - {ENV_NAME}_USER
    - {ENV_NAME}_PASSWORD
    - {ENV_NAME}_SCHEMA (optional)
    
    Args:
        env_name: Environment name (e.g., 'DEV', 'PREPROD', 'PROD', 'DEV_REVOPS')
        env_vars: Optional dictionary of environment variables (uses os.environ if None)
    
    Returns:
        Dictionary with connection parameters
    
    Raises:
        ValueError: If environment not found or missing required parameters
    
    Examples:
        >>> get_environment_config('DEV')
        {'host': 'localhost', 'port': 54391, 'database': 'ib-dl-it', 
         'user': 'kkrishna', 'password': '', 'schema': 'public'}
    """
    if env_vars is None:
        env_vars = os.environ
    
    # Normalize environment name to uppercase
    env_name = env_name.upper()
    
    # Get JDBC URL
    jdbc_url_key = f"{env_name}_JDBC_URL"
    jdbc_url = env_vars.get(jdbc_url_key)
    
    if not jdbc_url:
        raise ValueError(
            f"Environment '{env_name}' not found. "
            f"Missing environment variable: {jdbc_url_key}"
        )
    
    # Parse JDBC URL
    try:
        conn_params = parse_jdbc_url(jdbc_url)
    except ValueError as e:
        raise ValueError(f"Error parsing JDBC URL for environment '{env_name}': {e}")
    
    # Get user
    user_key = f"{env_name}_USER"
    user = env_vars.get(user_key)
    
    if not user:
        raise ValueError(
            f"Missing user for environment '{env_name}'. "
            f"Required environment variable: {user_key}"
        )
    
    # Get password (can be empty)
    password_key = f"{env_name}_PASSWORD"
    password = env_vars.get(password_key, '')
    
    # Get schema (optional, defaults to 'public')
    schema_key = f"{env_name}_SCHEMA"
    schema = env_vars.get(schema_key, 'public')
    
    # Build complete config
    config = {
        'host': conn_params['host'],
        'port': conn_params['port'],
        'database': conn_params['database'],
        'user': user,
        'password': password,
        'schema': schema
    }
    
    logger.info(f"Loaded environment config for '{env_name}': {conn_params['host']}:{conn_params['port']}/{conn_params['database']}")
    
    return config


def list_available_environments(env_vars: Dict[str, str] = None) -> list:
    """
    List all available Redshift environments defined in environment variables.
    
    Args:
        env_vars: Optional dictionary of environment variables (uses os.environ if None)
    
    Returns:
        List of environment names
    
    Examples:
        >>> list_available_environments()
        ['DEV', 'DEV_REVOPS', 'PREPROD', 'PROD']
    """
    if env_vars is None:
        env_vars = os.environ
    
    # Find all *_JDBC_URL variables
    environments = []
    for key in env_vars.keys():
        if key.endswith('_JDBC_URL'):
            env_name = key[:-9]  # Remove '_JDBC_URL' suffix
            environments.append(env_name)
    
    return sorted(environments)


def validate_environment_config(env_name: str, env_vars: Dict[str, str] = None) -> bool:
    """
    Validate that an environment has all required configuration.
    
    Args:
        env_name: Environment name
        env_vars: Optional dictionary of environment variables
    
    Returns:
        True if valid, False otherwise
    """
    try:
        get_environment_config(env_name, env_vars)
        return True
    except ValueError as e:
        logger.warning(f"Environment '{env_name}' validation failed: {e}")
        return False
