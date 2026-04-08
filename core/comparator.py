"""
Comparison engine for data validation.
Performs all validation checks and returns structured results.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Tuple, Optional
import logging

from utils.helpers import (
    parse_primary_keys,
    coerce_to_compare,
    compare_values,
    format_pk_values,
    get_common_columns,
    are_types_compatible
)

logger = logging.getLogger(__name__)


class Comparator:
    """
    Comparison engine that performs validation checks between two datasets.
    
    Supports:
    - Record count validation
    - Column count validation
    - Duplicate detection
    - Null value analysis
    - Empty string detection
    - Row-by-row data comparison
    - Metadata type validation
    """
    
    def __init__(self, source_df: pd.DataFrame, target_df: pd.DataFrame,
                 primary_keys: List[str] = None, validation_name: str = "Validation"):
        """
        Initialize comparator.
        
        Args:
            source_df: Source DataFrame
            target_df: Target DataFrame
            primary_keys: List of primary key column names
            validation_name: Name of this validation (for reporting)
        """
        self.source_df = source_df
        self.target_df = target_df
        self.primary_keys = primary_keys or []
        self.validation_name = validation_name
        self.common_cols = get_common_columns(source_df, target_df)
        self.subset_applied = False
        
        logger.info(f"Initialized comparator: {len(source_df)} source rows, "
                   f"{len(target_df)} target rows, {len(self.common_cols)} common columns")
    
    def run_all_checks(self, source_metadata: Dict[str, Any] = None, 
                      target_metadata: Dict[str, Any] = None,
                      subset_applied: bool = False) -> List[Dict[str, Any]]:
        """
        Run all validation checks.
        
        Args:
            source_metadata: Metadata from source adapter
            target_metadata: Metadata from target adapter
            subset_applied: Whether smart sub-setting was applied
        
        Returns:
            List of validation result dictionaries
        """
        self.subset_applied = subset_applied
        results = []
        
        logger.info("Running all validation checks...")
        
        # 1. Record count check
        results.append(self._check_record_counts())
        
        # 2. Column count check
        results.append(self._check_column_counts())
        
        # 3. Metadata type check
        if source_metadata and target_metadata:
            results.extend(self._check_metadata_types(source_metadata, target_metadata))
        
        # 4. Duplicate check
        results.extend(self._check_duplicates())
        
        # 5. Null check
        results.extend(self._check_nulls())
        
        # 6. Empty string check
        results.extend(self._check_empty_strings())
        
        # 7. Data validation
        results.extend(self._check_data_values())
        
        logger.info(f"Completed all checks: {len(results)} result records")
        
        return results
    
    def _check_record_counts(self) -> Dict[str, Any]:
        """Check and compare record counts."""
        source_count = len(self.source_df)
        target_count = len(self.target_df)
        match = source_count == target_count
        
        result_status = "PASS" if match else "FAIL"
        detail = f"Source: {source_count} rows, Target: {target_count} rows"
        
        if self.subset_applied:
            result_status = "PASS" if match else "FAIL"
            detail += " (Note: Smart sub-setting applied - records filtered to matching PKs)"
        
        return {
            "validation": "record_count_check",
            "result": result_status,
            "column": "",
            "pk": "",
            "detail": detail,
            "source_value": str(source_count),
            "target_value": str(target_count)
        }
    
    def _check_metadata_types(self, source_metadata: Dict[str, Any], 
                              target_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check for data type compatibility between common columns."""
        results = []
        
        # Create maps for easier lookup
        source_types = {c['name']: c['dtype'] for c in source_metadata.get('columns', [])}
        target_types = {c['name']: c['dtype'] for c in target_metadata.get('columns', [])}
        
        for col in self.common_cols:
            s_type = source_types.get(col)
            t_type = target_types.get(col)
            
            if s_type and t_type:
                if are_types_compatible(s_type, t_type):
                    results.append({
                        "validation": "metadata_type_check",
                        "result": "PASS",
                        "column": col,
                        "pk": "",
                        "detail": f"Compatible types: Source '{s_type}', Target '{t_type}'",
                        "source_value": s_type,
                        "target_value": t_type
                    })
                else:
                    results.append({
                        "validation": "metadata_type_check",
                        "result": "FAIL",
                        "column": col,
                        "pk": "",
                        "detail": f"Incompatible types: Source '{s_type}', Target '{t_type}'",
                        "source_value": s_type,
                        "target_value": t_type
                    })
        
        return results

    def _check_column_counts(self) -> Dict[str, Any]:
        """Check and compare column counts."""
        source_cols = len(self.source_df.columns)
        target_cols = len(self.target_df.columns)
        common_count = len(self.common_cols)
        
        source_only = set(self.source_df.columns) - set(self.target_df.columns)
        target_only = set(self.target_df.columns) - set(self.source_df.columns)
        
        details = [f"Source: {source_cols} columns, Target: {target_cols} columns, Common: {common_count}"]
        if source_only:
            details.append(f"Source-only: {sorted(source_only)}")
        if target_only:
            details.append(f"Target-only: {sorted(target_only)}")
        
        return {
            "validation": "column_count_check",
            "result": "PASS",
            "column": "",
            "pk": "",
            "detail": " | ".join(details),
            "source_value": str(source_cols),
            "target_value": str(target_cols)
        }
    
    def _check_duplicates(self) -> List[Dict[str, Any]]:
        """Check for duplicate primary keys."""
        results = []
        
        if not self.primary_keys:
            return [{
                "validation": "duplicate_check",
                "result": "SKIP",
                "column": "",
                "pk": "",
                "detail": "No primary key defined - duplicate check skipped",
                "source_value": "",
                "target_value": ""
            }]
        
        # Check source duplicates
        source_dups = self.source_df[self.primary_keys].duplicated(keep=False)
        source_dup_count = source_dups.sum()
        
        if source_dup_count > 0:
            dup_values = self.source_df[source_dups][self.primary_keys].drop_duplicates()
            for idx, row in dup_values.head(5).iterrows():  # Limit to first 5
                pk_vals = tuple(row[c] for c in self.primary_keys)
                pk_str = format_pk_values(pk_vals, self.primary_keys)
                count = ((self.source_df[self.primary_keys] == row).all(axis=1)).sum()
                results.append({
                    "validation": "duplicate_check",
                    "result": "FAIL",
                    "column": "",
                    "pk": pk_str,
                    "detail": f"Source has {count} duplicate rows (showing first 5 of {source_dup_count})",
                    "source_value": str(count),
                    "target_value": ""
                })
        else:
            results.append({
                "validation": "duplicate_check",
                "result": "PASS",
                "column": "",
                "pk": "",
                "detail": "No duplicates found in Source",
                "source_value": "0",
                "target_value": ""
            })
        
        # Check target duplicates
        target_dups = self.target_df[self.primary_keys].duplicated(keep=False)
        target_dup_count = target_dups.sum()
        
        if target_dup_count > 0:
            dup_values = self.target_df[target_dups][self.primary_keys].drop_duplicates()
            for idx, row in dup_values.head(5).iterrows():
                pk_vals = tuple(row[c] for c in self.primary_keys)
                pk_str = format_pk_values(pk_vals, self.primary_keys)
                count = ((self.target_df[self.primary_keys] == row).all(axis=1)).sum()
                results.append({
                    "validation": "duplicate_check",
                    "result": "FAIL",
                    "column": "",
                    "pk": pk_str,
                    "detail": f"Target has {count} duplicate rows (showing first 5 of {target_dup_count})",
                    "source_value": "",
                    "target_value": str(count)
                })
        else:
            results.append({
                "validation": "duplicate_check",
                "result": "PASS",
                "column": "",
                "pk": "",
                "detail": "No duplicates found in Target",
                "source_value": "",
                "target_value": "0"
            })
        
        return results
    
    def _check_nulls(self) -> List[Dict[str, Any]]:
        """Check for null/NA values in common columns."""
        results = []
        
        for col in self.common_cols:
            source_nulls = self.source_df[col].isna().sum()
            target_nulls = self.target_df[col].isna().sum()
            
            if source_nulls > 0 or target_nulls > 0:
                match = source_nulls == target_nulls
                results.append({
                    "validation": "null_check",
                    "result": "PASS" if match else "FAIL",
                    "column": col,
                    "pk": "",
                    "detail": f"Source: {source_nulls} nulls, Target: {target_nulls} nulls",
                    "source_value": str(source_nulls),
                    "target_value": str(target_nulls)
                })
        
        if not results:
            results.append({
                "validation": "null_check",
                "result": "PASS",
                "column": "",
                "pk": "",
                "detail": "No null values found in any common columns",
                "source_value": "0",
                "target_value": "0"
            })
        
        return results
    
    def _check_empty_strings(self) -> List[Dict[str, Any]]:
        """Check for empty strings in common columns."""
        failures = []
        
        def scan_df(df: pd.DataFrame, side_name: str):
            for col in self.common_cols:
                if col not in df.columns:
                    continue
                
                mask = df[col].astype(object) == ''
                empty_count = mask.sum()
                
                if empty_count > 0:
                    # Report first occurrence
                    for idx in df.index[mask][:3]:  # Limit to first 3
                        row = df.loc[idx]
                        pk_vals = tuple(row[c] if c in row else np.nan for c in self.primary_keys) if self.primary_keys else (idx,)
                        pk_str = format_pk_values(pk_vals, self.primary_keys) if self.primary_keys else f"index={idx}"
                        
                        failures.append({
                            "validation": "empty_string_check",
                            "result": "FAIL",
                            "column": col,
                            "pk": pk_str,
                            "detail": f"{side_name} contains empty string (showing first 3 of {empty_count})",
                            "source_value": "''" if side_name == "Source" else "",
                            "target_value": "''" if side_name == "Target" else ""
                        })
                    break  # Only show first column with empties
        
        scan_df(self.source_df, "Source")
        scan_df(self.target_df, "Target")
        
        if not failures:
            failures.append({
                "validation": "empty_string_check",
                "result": "PASS",
                "column": "",
                "pk": "",
                "detail": "No empty strings found",
                "source_value": "",
                "target_value": ""
            })
        
        return failures
    
    def _check_data_values(self) -> List[Dict[str, Any]]:
        """Compare data values between source and target."""
        failures = []
        
        # If no primary key, compare row-by-row
        if not self.primary_keys:
            return self._compare_without_pk()
        
        # With primary key, use key-based comparison
        return self._compare_with_pk()
    
    def _compare_without_pk(self) -> List[Dict[str, Any]]:
        """Compare data row-by-row without primary keys."""
        failures = []
        min_len = min(len(self.source_df), len(self.target_df))
        mismatch_count = 0
        
        for i in range(min_len):
            row_source = self.source_df.iloc[i]
            row_target = self.target_df.iloc[i]
            
            for col in self.common_cols:
                val_source = row_source.get(col, np.nan)
                val_target = row_target.get(col, np.nan)
                
                if not compare_values(val_source, val_target):
                    mismatch_count += 1
                    # Limit detailed failures to first 100
                    if len(failures) < 100:
                        failures.append({
                            "validation": "data_validation",
                            "result": "FAIL",
                            "column": col,
                            "pk": f"index={i}",
                            "detail": "Values do not match",
                            "source_value": repr(val_source)[:100],
                            "target_value": repr(val_target)[:100]
                        })
        
        if mismatch_count > 100:
            failures.append({
                "validation": "data_validation",
                "result": "INFO",
                "column": "",
                "pk": "",
                "detail": f"... and {mismatch_count - 100} more mismatches (showing first 100)",
                "source_value": "",
                "target_value": ""
            })
        
        if mismatch_count == 0:
            failures.append({
                "validation": "data_validation",
                "result": "PASS",
                "column": "",
                "pk": "",
                "detail": f"All {min_len} rows match across {len(self.common_cols)} common columns",
                "source_value": "",
                "target_value": ""
            })
        
        return failures
    
    def _compare_with_pk(self) -> List[Dict[str, Any]]:
        """Compare data using primary keys."""
        failures = []
        
        # Validate PK columns exist
        missing_source = [c for c in self.primary_keys if c not in self.source_df.columns]
        missing_target = [c for c in self.primary_keys if c not in self.target_df.columns]
        
        if missing_source or missing_target:
            return [{
                "validation": "data_validation",
                "result": "FAIL",
                "column": "",
                "pk": "",
                "detail": f"Primary key columns missing. Source: {missing_source}, Target: {missing_target}",
                "source_value": "",
                "target_value": ""
            }]
        
        # Set index to primary key
        # Remove duplicates for value comparison to prevent crashing
        # Duplicates are reported separately in _check_duplicates
        source_clean = self.source_df.drop_duplicates(subset=self.primary_keys)
        target_clean = self.target_df.drop_duplicates(subset=self.primary_keys)
        
        source_idx = source_clean.set_index(self.primary_keys, drop=False)
        target_idx = target_clean.set_index(self.primary_keys, drop=False)
        
        # Find common and unique primary key values
        common_index = source_idx.index.intersection(target_idx.index)
        source_only = source_idx.index.difference(target_idx.index)
        target_only = target_idx.index.difference(source_idx.index)
        
        # Report PK matching stats
        failures.append({
            "validation": "primary_key_match",
            "result": "PASS" if len(source_only) == 0 and len(target_only) == 0 else "FAIL",
            "column": "",
            "pk": "",
            "detail": f"Common: {len(common_index)}, Source-only: {len(source_only)}, Target-only: {len(target_only)}",
            "source_value": str(len(source_idx)),
            "target_value": str(len(target_idx))
        })
        
        # Report source-only records
        if len(source_only) > 0:
            for pk_tuple in list(source_only)[:5]:
                if not isinstance(pk_tuple, tuple):
                    pk_tuple = (pk_tuple,)
                pk_str = format_pk_values(pk_tuple, self.primary_keys)
                failures.append({
                    "validation": "primary_key_match",
                    "result": "FAIL",
                    "column": "",
                    "pk": pk_str,
                    "detail": f"Primary key exists in Source but not in Target (showing first 5 of {len(source_only)})",
                    "source_value": "EXISTS",
                    "target_value": "MISSING"
                })
        
        # Report target-only records
        if len(target_only) > 0:
            for pk_tuple in list(target_only)[:5]:
                if not isinstance(pk_tuple, tuple):
                    pk_tuple = (pk_tuple,)
                pk_str = format_pk_values(pk_tuple, self.primary_keys)
                failures.append({
                    "validation": "primary_key_match",
                    "result": "FAIL",
                    "column": "",
                    "pk": pk_str,
                    "detail": f"Primary key exists in Target but not in Source (showing first 5 of {len(target_only)})",
                    "source_value": "MISSING",
                    "target_value": "EXISTS"
                })
        
        if len(common_index) == 0:
            logger.warning("No matching primary key values found")
            return failures
        
        # Compare values for common records
        logger.info(f"Comparing {len(common_index)} matching records across {len(self.common_cols)} columns")
        
        mismatch_count = 0
        for col in self.common_cols:
            if col not in source_idx.columns or col not in target_idx.columns:
                continue
            
            source_col = source_idx.loc[common_index, col].astype(object).map(coerce_to_compare)
            target_col = target_idx.loc[common_index, col].astype(object).map(coerce_to_compare)
            
            unequal = ~((source_col.isna() & target_col.isna()) | (source_col == target_col))
            
            if unequal.any():
                col_mismatch = unequal.sum()
                mismatch_count += col_mismatch
                
                # Report summary for this column
                failures.append({
                    "validation": "data_validation",
                    "result": "FAIL",
                    "column": col,
                    "pk": "",
                    "detail": f"{col_mismatch} mismatches in column {col}",
                    "source_value": "",
                    "target_value": ""
                })
                
                # Show first few mismatches for this column
                shown = 0
                for pk_tuple in source_col.index[unequal]:
                    if shown >= 3:
                        break
                    
                    val_source = source_idx.loc[pk_tuple, col]
                    val_target = target_idx.loc[pk_tuple, col]
                    
                    if not isinstance(pk_tuple, tuple):
                        pk_tuple = (pk_tuple,)
                    
                    pk_str = format_pk_values(pk_tuple, self.primary_keys)
                    
                    failures.append({
                        "validation": "data_validation",
                        "result": "FAIL",
                        "column": col,
                        "pk": pk_str,
                        "detail": f"Value mismatch (example {shown+1} of {col_mismatch})",
                        "source_value": repr(val_source)[:100],
                        "target_value": repr(val_target)[:100]
                    })
                    shown += 1
        
        if mismatch_count == 0:
            failures.append({
                "validation": "data_validation",
                "result": "PASS",
                "column": "",
                "pk": "",
                "detail": f"All values match for {len(common_index)} common records across {len(self.common_cols)} columns",
                "source_value": "",
                "target_value": ""
            })
        
        return failures
