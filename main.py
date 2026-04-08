"""
Universal Data Validation Framework
Main CLI entry point.

Usage:
    python main.py --config config/validations.yaml
    python main.py --config config/validations.yaml --name "CSV to Redshift"
    python main.py --config config/validations.yaml --output ./my_results
"""
import argparse
import logging
import sys
from pathlib import Path

from core import run_validations

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Universal Data Validation Framework',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all validations in config file
  python main.py --config config/validations.yaml
  
  # Run specific validation by name
  python main.py --config config/validations.yaml --name "CSV to Redshift"
  
  # Specify output directory
  python main.py --config config/validations.yaml --output ./results
  
  # Enable debug logging
  python main.py --config config/validations.yaml --debug

Configuration file format (YAML):
  validations:
    - name: "My Validation"
      source:
        type: file  # or table, datasource
        path: ./data/source.csv
      target:
        type: table
        schema: public
        table: my_table
      primary_keys: id,user_id
      output_dir: ./results
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        required=True,
        help='Path to YAML configuration file'
    )
    
    parser.add_argument(
        '--name', '-n',
        help='Name of specific validation to run (runs all if not specified)'
    )
    
    parser.add_argument(
        '--output', '-o',
        help='Output directory for reports (overrides config)'
    )
    
    parser.add_argument(
        '--debug', '-d',
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()
    
    # Set log level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validate config file exists
    config_path = Path(args.config)
    if not config_path.exists():
        logger.error(f"Configuration file not found: {config_path}")
        sys.exit(1)
    
    try:
        # Run validations
        results = run_validations(config_path, args.name)
        
        # Exit with error code if any validation failed
        failed_count = len([r for r in results if r['status'] == 'FAIL'])
        
        if failed_count > 0:
            logger.error(f"{failed_count} validation(s) failed")
            sys.exit(1)
        else:
            logger.info("All validations passed!")
            sys.exit(0)
    
    except Exception as e:
        logger.exception(f"Validation failed with error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
