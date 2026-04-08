"""
Main validator orchestrator.
Coordinates the validation workflow: loading data, running comparisons, generating reports.
"""
import yaml
from pathlib import Path
from typing import Dict, Any, List
import logging

from adapters import FileAdapter, TableAdapter, DataSourceAdapter, BaseAdapter
from core.comparator import Comparator
from core.reporter import Reporter
from utils.helpers import parse_primary_keys, resolve_path

logger = logging.getLogger(__name__)


class Validator:
    """
    Main validator orchestrator.
    
    Coordinates the entire validation workflow:
    1. Load configuration
    2. Instantiate appropriate adapters
    3. Load data from source and target
    4. Run comparisons
    5. Generate reports
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize validator with configuration.
        
        Args:
            config: Validation configuration dictionary
        """
        self.config = config
        self.name = config.get('name', 'Validation')
        self.source_config = config.get('source', {})
        self.target_config = config.get('target', {})
        self.primary_keys = [pk.lower() for pk in parse_primary_keys(config.get('primary_keys', ''))]
        self.output_dir = Path(config.get('output_dir', './results'))
        
        # Propagate common file settings from root config to source and target
        common_settings = ['sep', 'encoding', 'format', 'sheet_name', 'json_orient']
        for setting in common_settings:
            if setting in config:
                if setting not in self.source_config:
                    self.source_config[setting] = config[setting]
                if setting not in self.target_config:
                    self.target_config[setting] = config[setting]
        
        logger.info(f"Initialized validator: {self.name}")
    
    def _create_adapter(self, adapter_config: Dict[str, Any]) -> BaseAdapter:
        """
        Create appropriate adapter based on configuration.
        
        Args:
            adapter_config: Adapter configuration
        
        Returns:
            Instantiated adapter
        """
        adapter_type = adapter_config['type'].lower()
        
        if adapter_type == 'file':
            return FileAdapter(adapter_config)
        elif adapter_type == 'table':
            return TableAdapter(adapter_config)
        elif adapter_type == 'datasource':
            return DataSourceAdapter(adapter_config)
        else:
            raise ValueError(f"Unknown adapter type: {adapter_type}")
    
    def run(self) -> Dict[str, Any]:
        """
        Run the validation.
        
        Returns:
            Dictionary with validation results and report paths
        """
        logger.info("="*80)
        logger.info(f"STARTING VALIDATION: {self.name}")
        logger.info("="*80)
        
        # Create adapters
        logger.info("Creating adapters...")
        source_adapter = self._create_adapter(self.source_config)
        target_adapter = self._create_adapter(self.target_config)
        
        logger.info(f"Source: {source_adapter}")
        logger.info(f"Target: {target_adapter}")
        
        # Load data
        logger.info("\nLoading data...")
        source_df = source_adapter.load()
        target_df = target_adapter.load()
        
        # Get metadata
        source_metadata = source_adapter.get_metadata()
        target_metadata = target_adapter.get_metadata()
        
        logger.info(f"Source: {len(source_df)} rows, {len(source_df.columns)} columns")
        logger.info(f"Target: {len(target_df)} rows, {len(target_df.columns)} columns")
        
        # Smart Sub-setting Logic
        subset_applied = False
        if self.primary_keys and len(source_df) != len(target_df):
            logger.info("Dataset sizes differ. Applying smart sub-setting based on primary keys...")
            
            if len(source_df) < len(target_df):
                logger.info(f"Source ({len(source_df)}) is smaller than Target ({len(target_df)}). Filtering Target...")
                # Take PKs from source
                source_pks = source_df[self.primary_keys].drop_duplicates()
                # Filter target
                original_target_len = len(target_df)
                target_df = target_df.merge(source_pks, on=self.primary_keys, how='inner')
                logger.info(f"Target filtered from {original_target_len} to {len(target_df)} rows")
                subset_applied = True
            else:
                logger.info(f"Target ({len(target_df)}) is smaller than Source ({len(source_df)}). Filtering Source...")
                # Take PKs from target
                target_pks = target_df[self.primary_keys].drop_duplicates()
                # Filter source
                original_source_len = len(source_df)
                source_df = source_df.merge(target_pks, on=self.primary_keys, how='inner')
                logger.info(f"Source filtered from {original_source_len} to {len(source_df)} rows")
                subset_applied = True

        # Run comparison
        logger.info("\nRunning comparisons...")
        comparator = Comparator(
            source_df=source_df,
            target_df=target_df,
            primary_keys=self.primary_keys,
            validation_name=self.name
        )
        
        # Pass metadata for type checking
        results = comparator.run_all_checks(
            source_metadata=source_metadata,
            target_metadata=target_metadata,
            subset_applied=subset_applied
        )
        
        # Generate reports
        logger.info("\nGenerating reports...")
        reporter = Reporter(
            validation_name=self.name,
            results=results,
            source_metadata=source_metadata,
            target_metadata=target_metadata
        )
        
        report_paths = reporter.generate_reports(self.output_dir)
        
        # Summary
        fail_count = len([r for r in results if r['result'] == 'FAIL'])
        pass_count = len([r for r in results if r['result'] == 'PASS'])
        
        logger.info("\n" + "="*80)
        if fail_count > 0:
            logger.warning(f"VALIDATION FAILED: {pass_count} passed, {fail_count} failed")
        else:
            logger.info(f"VALIDATION PASSED: {pass_count} passed, {fail_count} failed")
        logger.info(f"CSV Report: {report_paths['csv']}")
        logger.info(f"HTML Report: {report_paths['html']}")
        logger.info("="*80 + "\n")
        
        return {
            'name': self.name,
            'status': 'PASS' if fail_count == 0 else 'FAIL',
            'pass_count': pass_count,
            'fail_count': fail_count,
            'total_count': len(results),
            'results': results,
            'reports': report_paths
        }


def load_config(config_path: Path) -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to YAML configuration file
    
    Returns:
        Configuration dictionary
    """
    logger.info(f"Loading configuration from: {config_path}")
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    return config


def run_validations(config_path: Path, validation_name: str = None) -> List[Dict[str, Any]]:
    """
    Run validations from configuration file.
    
    Args:
        config_path: Path to YAML configuration file
        validation_name: Optional name of specific validation to run (runs all if None)
    
    Returns:
        List of validation results
    """
    config = load_config(config_path)
    
    # Get list of validations
    validations = config.get('validations', [])
    
    if not validations:
        raise ValueError("No validations found in configuration file")
    
    # Filter by name if specified
    if validation_name:
        validations = [v for v in validations if v.get('name') == validation_name]
        if not validations:
            raise ValueError(f"Validation '{validation_name}' not found in configuration")
    
    # Run each validation
    results = []
    for val_config in validations:
        validator = Validator(val_config)
        result = validator.run()
        results.append(result)
    
    # Overall summary
    logger.info("\n" + "="*80)
    logger.info("OVERALL SUMMARY")
    logger.info("="*80)
    
    total_validations = len(results)
    passed_validations = len([r for r in results if r['status'] == 'PASS'])
    failed_validations = len([r for r in results if r['status'] == 'FAIL'])
    
    for result in results:
        status_icon = '✅' if result['status'] == 'PASS' else '❌'
        logger.info(f"{status_icon} {result['name']}: {result['pass_count']} passed, {result['fail_count']} failed")
    
    logger.info("="*80)
    logger.info(f"Total: {passed_validations}/{total_validations} validations passed")
    logger.info("="*80 + "\n")
    
    return results
