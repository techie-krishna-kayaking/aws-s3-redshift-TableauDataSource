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
        self.quick_sample_pks = config.get('quick_sample_pks', None)
        self.quick_sample_seed = int(config.get('quick_sample_seed', 42))

        if self.quick_sample_pks is not None:
            try:
                self.quick_sample_pks = int(self.quick_sample_pks)
            except (TypeError, ValueError):
                raise ValueError("'quick_sample_pks' must be a positive integer")
            if self.quick_sample_pks <= 0:
                raise ValueError("'quick_sample_pks' must be a positive integer")
        
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

    def _build_target_pk_candidates(self, source_pk_columns: List[str]) -> List[List[str]]:
        """Build candidate target PK column lists for pushdown filtering."""
        candidates: List[List[str]] = []

        mapped = [self.column_mapping.get(pk, pk) for pk in source_pk_columns]
        candidates.append(mapped)

        candidates.append(source_pk_columns)

        stripped = [
            self._strip_known_prefixes(pk, self.source_prefixes_to_strip)
            for pk in source_pk_columns
        ]
        candidates.append(stripped)

        deduped: List[List[str]] = []
        seen = set()
        for candidate in candidates:
            key = tuple(candidate)
            if key in seen:
                continue
            if not all(str(col).strip() for col in candidate):
                continue
            deduped.append(candidate)
            seen.add(key)

        return deduped
    
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
        subset_applied = False
        
        logger.info(f"Source: {len(source_df)} rows, {len(source_df.columns)} columns")
        
        # Smart quick mode: sample source PKs and push down target fetch by PK.
        if self.quick_sample_pks and isinstance(target_adapter, TableAdapter):
            source_pk_cols = [pk for pk in self.primary_keys if pk in source_df.columns]

            if not self.primary_keys:
                logger.warning("quick_sample_pks requested but no primary_keys configured; using regular target load")
                target_df = target_adapter.load()
                target_metadata = target_adapter.get_metadata()
            elif len(source_pk_cols) != len(self.primary_keys):
                logger.warning(
                    "quick_sample_pks requested but some PKs are missing in source. Found %s of %s PKs; using regular target load",
                    len(source_pk_cols),
                    len(self.primary_keys)
                )
                target_df = target_adapter.load()
                target_metadata = target_adapter.get_metadata()
            else:
                source_unique_pks = source_df[source_pk_cols].drop_duplicates()
                sample_size = min(self.quick_sample_pks, len(source_unique_pks))

                if sample_size <= 0:
                    logger.warning("Source has no PK rows for quick sampling; using regular target load")
                    target_df = target_adapter.load()
                    target_metadata = target_adapter.get_metadata()
                else:
                    if sample_size < len(source_unique_pks):
                        sampled_pks = source_unique_pks.sample(n=sample_size, random_state=self.quick_sample_seed)
                    else:
                        sampled_pks = source_unique_pks

                    source_df = source_df.merge(sampled_pks, on=source_pk_cols, how='inner')
                    logger.info(
                        "Quick mode enabled: sampled %s PK rows from source (%s total unique PKs)",
                        sample_size,
                        len(source_unique_pks)
                    )

                    pk_values = list(sampled_pks.itertuples(index=False, name=None))
                    pushdown_loaded = False
                    last_error = None

                    for target_pk_cols in self._build_target_pk_candidates(source_pk_cols):
                        try:
                            target_df = target_adapter.load(pk_columns=target_pk_cols, pk_values=pk_values)
                            target_metadata = target_adapter.get_metadata()
                            logger.info(
                                "Quick mode target pushdown succeeded using PK columns: %s",
                                target_pk_cols
                            )
                            pushdown_loaded = True
                            subset_applied = True
                            break
                        except Exception as e:
                            last_error = e
                            logger.warning(
                                "Quick mode target pushdown failed for PK columns %s: %s",
                                target_pk_cols,
                                e
                            )

                    if not pushdown_loaded:
                        logger.warning(
                            "Quick mode pushdown failed (%s). Falling back to regular target load.",
                            last_error
                        )
                        target_df = target_adapter.load()
                        target_metadata = target_adapter.get_metadata()
        else:
            # Default target load path
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
        # Filter primary keys to only those that exist in both source and target
        valid_pks = [pk for pk in self.primary_keys if pk in source_df.columns and pk in target_df.columns]
        
        logger.info(f"PK check: configured {len(self.primary_keys)} PKs {self.primary_keys}, found {len(valid_pks)} valid PKs {valid_pks}")
        
        # Log valid PKs status
        if self.primary_keys and not valid_pks:
            logger.warning(f"Primary key columns {self.primary_keys} not fully available in dataframes. Source has {list(source_df.columns[:5])}..., Target has {list(target_df.columns[:5])}...")
        
        if valid_pks and len(source_df) != len(target_df):
            logger.info(f"Dataset sizes differ: {len(source_df)} source vs {len(target_df)} target. Attempting smart sub-setting...")
            
            if len(source_df) < len(target_df):
                logger.info(f"Source ({len(source_df)}) is smaller than Target ({len(target_df)}). Attempting to filter Target with PKs {valid_pks}...")
                try:
                    # Take PKs from source
                    source_pks = source_df[valid_pks].drop_duplicates()
                    # Filter target
                    original_target_len = len(target_df)
                    target_df_filtered = target_df.merge(source_pks, on=valid_pks, how='inner')
                    
                    # Check if merge resulted in 0 rows (no matching PKs)
                    if len(target_df_filtered) == 0:
                        logger.warning(f"Smart sub-setting would result in 0 rows (no matching PK values between source and target). Skipping filtering and using full datasets.")
                        # Restore original target_df
                        target_df = target_df
                    else:
                        target_df = target_df_filtered
                        logger.info(f"Target filtered from {original_target_len} to {len(target_df)} rows")
                        subset_applied = True
                except KeyError as e:
                    logger.warning(f"Could not perform PK-based filtering: {e}. Proceeding without filtering.")
            else:
                logger.info(f"Target ({len(target_df)}) is smaller than Source ({len(source_df)}). Attempting to filter Source with PKs {valid_pks}...")
                try:
                    # Take PKs from target
                    target_pks = target_df[valid_pks].drop_duplicates()
                    # Filter source
                    original_source_len = len(source_df)
                    source_df_filtered = source_df.merge(target_pks, on=valid_pks, how='inner')
                    
                    # Check if merge resulted in 0 rows (no matching PKs)
                    if len(source_df_filtered) == 0:
                        logger.warning(f"Smart sub-setting would result in 0 rows (no matching PK values between source and target). Skipping filtering and using full datasets.")
                        # Restore original source_df
                        source_df = source_df
                    else:
                        source_df = source_df_filtered
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


def run_validations(
    config_path: Path,
    validation_name: str = None,
    target_limit: int = None,
    quick_sample_pks: int = None
) -> List[Dict[str, Any]]:
    """
    Run validations from configuration file.
    
    Args:
        config_path: Path to YAML configuration file
        validation_name: Optional name of specific validation to run (runs all if None)
        target_limit: Optional row limit applied to target table adapters for quick runs
        quick_sample_pks: Optional source PK sample size for target pushdown quick mode
    
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
        if target_limit is not None:
            target_cfg = val_config.get('target', {})
            if str(target_cfg.get('type', '')).lower() == 'table':
                target_cfg['limit'] = target_limit
                val_config['target'] = target_cfg

        if quick_sample_pks is not None:
            val_config['quick_sample_pks'] = quick_sample_pks

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
        logger.info(f"Consolidated CSV:  {consolidated_paths['csv']}")
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
