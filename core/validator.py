"""
Main validator orchestrator.
Coordinates the validation workflow: loading data, running comparisons, generating reports.
"""
import shutil
import yaml
from pathlib import Path
from typing import Dict, Any, List
import logging
from collections import defaultdict

from adapters import FileAdapter, TableAdapter, DataSourceAdapter, BaseAdapter
from core.comparator import Comparator
from core.reporter import Reporter, ConsolidatedReporter
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
        self.regression = config.get('regression', False)  # Enable comprehensive validations
        self.column_mapping = {
            str(src).lower(): str(tgt).lower()
            for src, tgt in (config.get('column_mapping', {}) or {}).items()
        }
        self.auto_match_by_suffix = bool(config.get('auto_match_by_suffix', False))
        self.source_prefixes_to_strip = [
            str(p).lower() for p in (config.get('source_prefixes_to_strip', []) or []) if str(p).strip()
        ]
        self.target_prefixes_to_strip = [
            str(p).lower() for p in (config.get('target_prefixes_to_strip', []) or []) if str(p).strip()
        ]
        
        # Propagate common file settings from root config to source and target
        common_settings = ['sep', 'encoding', 'format', 'sheet_name', 'json_orient']
        for setting in common_settings:
            if setting in config:
                if setting not in self.source_config:
                    self.source_config[setting] = config[setting]
                if setting not in self.target_config:
                    self.target_config[setting] = config[setting]
        
        logger.info(f"Initialized validator: {self.name}")

    @staticmethod
    def _strip_known_prefixes(column_name: str, prefixes: List[str]) -> str:
        """Strip configured prefixes from a column name if present."""
        for prefix in prefixes:
            if column_name.startswith(prefix):
                return column_name[len(prefix):]
        return column_name

    def _candidate_column_names(self, column_name: str, prefixes: List[str]) -> List[str]:
        """Generate candidate normalized names for fuzzy matching."""
        stripped = self._strip_known_prefixes(column_name, prefixes)
        if stripped == column_name:
            return [column_name]
        return [column_name, stripped]

    def _is_suffix_match(self, source_name: str, target_name: str) -> bool:
        """Check if one name is a suffix-based variant of the other."""
        return (
            source_name.endswith(f"_{target_name}")
            or target_name.endswith(f"_{source_name}")
        )

    def _resolve_column_alignment(
        self,
        source_columns: List[str],
        target_columns: List[str]
    ) -> Dict[str, str]:
        """
        Resolve source->target alignment map for column names.

        Priority:
        1) Explicit mapping from config.column_mapping
        2) Exact name match
        3) Optional fuzzy matching using configured prefixes and suffix matching
        """
        target_set = set(target_columns)
        rename_map: Dict[str, str] = {}
        used_targets = set()

        # Explicit mapping first.
        for src_col, tgt_col in self.column_mapping.items():
            if src_col not in source_columns:
                logger.warning(
                    "Configured source column '%s' not found for mapping", src_col
                )
                continue
            if tgt_col not in target_set:
                logger.warning(
                    "Configured target column '%s' not found for mapping from '%s'", tgt_col, src_col
                )
                continue
            rename_map[src_col] = tgt_col
            used_targets.add(tgt_col)

        if not self.auto_match_by_suffix and not self.source_prefixes_to_strip and not self.target_prefixes_to_strip:
            return rename_map

        candidates_by_source = defaultdict(list)
        for src_col in source_columns:
            if src_col in rename_map:
                continue
            if src_col in target_set and src_col not in used_targets:
                rename_map[src_col] = src_col
                used_targets.add(src_col)
                continue

            src_candidates = self._candidate_column_names(src_col, self.source_prefixes_to_strip)
            for tgt_col in target_columns:
                if tgt_col in used_targets:
                    continue

                tgt_candidates = self._candidate_column_names(tgt_col, self.target_prefixes_to_strip)
                matched = False

                if set(src_candidates).intersection(tgt_candidates):
                    matched = True
                elif self.auto_match_by_suffix:
                    for sc in src_candidates:
                        for tc in tgt_candidates:
                            if self._is_suffix_match(sc, tc):
                                matched = True
                                break
                        if matched:
                            break

                if matched:
                    candidates_by_source[src_col].append(tgt_col)

        for src_col, target_candidates in candidates_by_source.items():
            if len(target_candidates) == 1:
                tgt_col = target_candidates[0]
                rename_map[src_col] = tgt_col
                used_targets.add(tgt_col)
            elif len(target_candidates) > 1:
                logger.warning(
                    "Ambiguous auto column mapping for source '%s': %s. Add explicit column_mapping to resolve.",
                    src_col,
                    sorted(target_candidates)
                )

        return rename_map

    def _apply_column_alignment(
        self,
        source_df,
        target_df,
        source_metadata: Dict[str, Any],
        target_metadata: Dict[str, Any]
    ):
        """Apply column renames on source so source/target names can be compared consistently."""
        source_columns = list(source_df.columns)
        target_columns = list(target_df.columns)

        rename_map = self._resolve_column_alignment(source_columns, target_columns)

        # Keep only real renames where target column exists.
        source_rename_map = {
            src: tgt
            for src, tgt in rename_map.items()
            if src in source_df.columns and tgt in target_df.columns and src != tgt
        }

        if source_rename_map:
            logger.info(
                "Applying source column alignment for %d columns", len(source_rename_map)
            )
            source_df = source_df.rename(columns=source_rename_map)
            for col_meta in source_metadata.get('columns', []):
                col_name = col_meta.get('name')
                if col_name in source_rename_map:
                    col_meta['name'] = source_rename_map[col_name]

        # Normalize PKs to aligned target-style names when source-prefixed PKs are provided.
        aligned_primary_keys = []
        for pk in self.primary_keys:
            aligned_pk = rename_map.get(pk, pk)
            aligned_primary_keys.append(aligned_pk)

        self.primary_keys = aligned_primary_keys

        if self.column_mapping or self.auto_match_by_suffix or self.source_prefixes_to_strip or self.target_prefixes_to_strip:
            common_after_alignment = set(source_df.columns).intersection(set(target_df.columns))
            logger.info(
                "Column alignment complete: %d source columns, %d target columns, %d common columns",
                len(source_df.columns),
                len(target_df.columns),
                len(common_after_alignment)
            )

        return source_df, target_df, source_metadata, target_metadata
    
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
        source_metadata = source_adapter.get_metadata()
        
        logger.info(f"Source: {len(source_df)} rows, {len(source_df.columns)} columns")
        
        # Load target without pushdown filtering initially
        # (will use pushdown after column alignment if source is smaller)
        target_df = target_adapter.load()
        target_metadata = target_adapter.get_metadata()

        # Align columns when source and target naming conventions differ.
        source_df, target_df, source_metadata, target_metadata = self._apply_column_alignment(
            source_df=source_df,
            target_df=target_df,
            source_metadata=source_metadata,
            target_metadata=target_metadata
        )
        
        logger.info(f"Source: {len(source_df)} rows, {len(source_df.columns)} columns")
        logger.info(f"Target: {len(target_df)} rows, {len(target_df.columns)} columns")
        
        # Smart Sub-setting Logic
        subset_applied = False
        # Filter primary keys to only those that exist in both source and target
        valid_pks = [pk for pk in self.primary_keys if pk in source_df.columns and pk in target_df.columns]
        
        # Log valid PKs status
        if self.primary_keys and not valid_pks:
            logger.warning(f"Primary key columns {self.primary_keys} not fully available in dataframes. Source has {list(source_df.columns[:5])}..., Target has {list(target_df.columns[:5])}...")
        
        if valid_pks and len(source_df) != len(target_df):
            logger.info("Dataset sizes differ. Applying smart sub-setting based on primary keys...")
            
            if len(source_df) < len(target_df):
                logger.info(f"Source ({len(source_df)}) is smaller than Target ({len(target_df)}). Filtering Target with PKs {valid_pks}...")
                try:
                    # Take PKs from source
                    source_pks = source_df[valid_pks].drop_duplicates()
                    # Filter target
                    original_target_len = len(target_df)
                    target_df = target_df.merge(source_pks, on=valid_pks, how='inner')
                    logger.info(f"Target filtered from {original_target_len} to {len(target_df)} rows")
                    subset_applied = True
                except KeyError as e:
                    logger.warning(f"Could not perform PK-based filtering: {e}. Proceeding without filtering.")
            else:
                logger.info(f"Target ({len(target_df)}) is smaller than Source ({len(source_df)}). Filtering Source with PKs {valid_pks}...")
                try:
                    # Take PKs from target
                    target_pks = target_df[valid_pks].drop_duplicates()
                    # Filter source
                    original_source_len = len(source_df)
                    source_df = source_df.merge(target_pks, on=valid_pks, how='inner')
                    logger.info(f"Source filtered from {original_source_len} to {len(source_df)} rows")
                    subset_applied = True
                except KeyError as e:
                    logger.warning(f"Could not perform PK-based filtering: {e}. Proceeding without filtering.")
        elif self.primary_keys and not valid_pks:
            logger.warning(f"No valid primary keys found in dataframes. Configured PKs {self.primary_keys} not found in both source and target. Skipping smart sub-setting.")

        # Run comparison
        logger.info("\nRunning comparisons...")
        # Use only valid PKs for comparison (those that exist in both dataframes)
        comparator = Comparator(
            source_df=source_df,
            target_df=target_df,
            primary_keys=valid_pks if valid_pks else self.primary_keys,
            validation_name=self.name,
            regression_mode=self.regression
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
            'reports': report_paths,
            'source_metadata': source_metadata,
            'target_metadata': target_metadata
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
    
    # Generate consolidated reports if multiple validations
    if len(results) > 1:
        # Use the output_dir from the first validation
        output_dir = Path(validations[0].get('output_dir', './results'))
        consolidated = ConsolidatedReporter(results)
        consolidated_paths = consolidated.generate_reports(output_dir)
        logger.info(f"Consolidated Excel: {consolidated_paths['excel']}")
        logger.info(f"Consolidated HTML:  {consolidated_paths['html']}")

        # Move individual CSV/HTML files to archive subfolder
        archive_dir = output_dir / 'archive'
        archive_dir.mkdir(parents=True, exist_ok=True)
        for r in results:
            for report_path in r.get('reports', {}).values():
                report_path = Path(report_path)
                if report_path.exists():
                    shutil.move(str(report_path), str(archive_dir / report_path.name))
        logger.info(f"Individual reports moved to: {archive_dir}")
    
    return results
