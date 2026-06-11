#!/usr/bin/env python3
"""
Metadata-only Validator
Compares ONLY:
  1. Row count (source vs target)
  2. Column count (source vs target)

No column-level or row-level data validation.
"""

import csv
import html
import yaml
import logging
import pandas as pd
import redshift_connector
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from utils.helpers import load_environment
from utils.env_config import get_environment_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class MetadataValidator:
    """Simple validator for row/column count comparison only."""
    
    def __init__(self, config_path: str):
        """Initialize with YAML config."""
        with open(config_path, 'r') as f:
            self.full_config = yaml.safe_load(f)
        self.validations = self.full_config.get('validations', [])
        self.results = []
        self.redshift_conn = None
        self._init_redshift()
    
    def _init_redshift(self):
        """Initialize Redshift connection using PREPROD environment."""
        try:
            env = load_environment()
            env_config = get_environment_config('PREPROD', env)
            
            logger.info(f"Connecting to Redshift: {env_config['host']}:{env_config['port']}/{env_config['database']}")
            self.redshift_conn = redshift_connector.connect(
                host=env_config['host'],
                database=env_config['database'],
                user=env_config['user'],
                password=env_config['password'],
                port=env_config['port']
            )
            logger.info("✓ Redshift connection established")
        except Exception as e:
            logger.error(f"Failed to connect to Redshift: {e}")
            raise
    
    def get_csv_metadata(self, csv_path: str) -> Tuple[int, int]:
        """Get row and column count from CSV."""
        try:
            df = pd.read_csv(csv_path, nrows=None)
            rows = len(df)
            cols = len(df.columns)
            return rows, cols
        except Exception as e:
            logger.error(f"Error reading CSV {csv_path}: {e}")
            return None, None
    
    def _get_redshift_query_result(self, query: str) -> Optional[int]:
        """Execute a single query and return first result, or None on error."""
        try:
            cursor = self.redshift_conn.cursor()
            cursor.execute(query)
            result = cursor.fetchone()
            cursor.close()
            return result[0] if result else None
        except Exception as e:
            logger.debug(f"Query error: {e}")
            # Try to recover transaction
            try:
                self.redshift_conn.rollback()
            except:
                pass
            return None
    
    def get_table_metadata(self, schema: str, table: str) -> Tuple[Optional[int], Optional[int]]:
        """Get row and column count from Redshift table."""
        if not self.redshift_conn:
            logger.error("Not connected to Redshift")
            return None, None
        
        rows = self._get_redshift_query_result(f"SELECT COUNT(*) FROM {schema}.{table}")
        cols = self._get_redshift_query_result(
            f"SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='{schema}' AND table_name='{table}'"
        )
        
        return rows, cols
    
    def validate_all(self) -> List[Dict]:
        """Run metadata validation for all configs."""
        for i, validation in enumerate(self.validations, 1):
            name = validation.get('name', f'validation_{i}')
            logger.info(f"\n[{i}/{len(self.validations)}] Validating: {name}")
            
            # Get source CSV metadata
            source_config = validation.get('source', {})
            csv_path = source_config.get('path', '')
            source_rows, source_cols = self.get_csv_metadata(csv_path)
            
            if source_rows is None:
                logger.error(f"  ✗ Failed to read CSV: {csv_path}")
                self.results.append({
                    'name': name,
                    'csv_file': csv_path,
                    'csv_rows': 'ERROR',
                    'csv_cols': 'ERROR',
                    'table': validation.get('target', {}).get('table', ''),
                    'table_rows': 'N/A',
                    'table_cols': 'N/A',
                    'rows_match': 'ERROR',
                    'cols_match': 'ERROR',
                    'status': 'FAILED'
                })
                continue
            
            logger.info(f"  CSV: {source_rows} rows, {source_cols} columns")
            
            # Get target table metadata
            target_config = validation.get('target', {})
            schema = target_config.get('schema', 'edw_asis')
            table = target_config.get('table', '')
            target_rows, target_cols = self.get_table_metadata(schema, table)
            
            if target_rows is None:
                logger.error(f"  ✗ Failed to query table: {schema}.{table}")
                self.results.append({
                    'name': name,
                    'csv_file': csv_path,
                    'csv_rows': source_rows,
                    'csv_cols': source_cols,
                    'table': table,
                    'table_rows': 'ERROR',
                    'table_cols': 'ERROR',
                    'rows_match': 'ERROR',
                    'cols_match': 'ERROR',
                    'status': 'FAILED'
                })
                continue
            
            logger.info(f"  Table: {target_rows} rows, {target_cols} columns")
            
            # Compare
            rows_match = source_rows == target_rows
            cols_match = source_cols == target_cols
            status = 'PASSED' if (rows_match and cols_match) else 'FAILED'
            
            if rows_match and cols_match:
                logger.info(f"  ✓ MATCH - Rows and columns match")
            else:
                if not rows_match:
                    logger.warning(f"  ✗ Row count mismatch: CSV={source_rows}, Table={target_rows}")
                if not cols_match:
                    logger.warning(f"  ✗ Column count mismatch: CSV={source_cols}, Table={target_cols}")
            
            self.results.append({
                'name': name,
                'csv_file': csv_path,
                'csv_rows': source_rows,
                'csv_cols': source_cols,
                'table': table,
                'table_rows': target_rows,
                'table_cols': target_cols,
                'rows_match': 'YES' if rows_match else 'NO',
                'cols_match': 'YES' if cols_match else 'NO',
                'status': status
            })
        
        return self.results

        def _generate_html_report(self, html_file: Path):
                """Generate a single sortable HTML table report."""
                columns = [
                        'name', 'csv_file', 'csv_rows', 'csv_cols',
                        'table', 'table_rows', 'table_cols',
                        'rows_match', 'cols_match', 'status'
                ]

                rows_html = []
                for row in self.results:
                        cells = ''.join(f"<td>{html.escape(str(row.get(col, '')))}</td>" for col in columns)
                        rows_html.append(f"<tr>{cells}</tr>")

                table_rows = '\n'.join(rows_html)
                headers = ''.join(
                        f'<th onclick="sortTable({idx})">{html.escape(col)}</th>'
                        for idx, col in enumerate(columns)
                )

                html_content = f"""<!doctype html>
<html lang=\"en\">
<head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Metadata Validation Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 20px; color: #1f2937; }}
        h1 {{ margin: 0 0 8px; }}
        .meta {{ margin-bottom: 16px; color: #4b5563; }}
        table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
        th, td {{ border: 1px solid #d1d5db; padding: 8px; text-align: left; }}
        th {{ background: #f3f4f6; cursor: pointer; position: sticky; top: 0; }}
        tr:nth-child(even) {{ background: #f9fafb; }}
    </style>
</head>
<body>
    <h1>Metadata Validation Report</h1>
    <div class=\"meta\">Only metadata checks: row count and column count.</div>
    <table id=\"reportTable\">
        <thead>
            <tr>{headers}</tr>
        </thead>
        <tbody>
            {table_rows}
        </tbody>
    </table>
    <script>
        let sortDirections = {{}};
        function tryParseNumber(value) {{
            const n = Number(value);
            return Number.isNaN(n) ? null : n;
        }}
        function sortTable(colIndex) {{
            const table = document.getElementById('reportTable');
            const tbody = table.tBodies[0];
            const rows = Array.from(tbody.rows);
            const dir = sortDirections[colIndex] === 'asc' ? 'desc' : 'asc';
            sortDirections[colIndex] = dir;
            rows.sort((a, b) => {{
                const av = a.cells[colIndex].innerText.trim();
                const bv = b.cells[colIndex].innerText.trim();
                const an = tryParseNumber(av);
                const bn = tryParseNumber(bv);
                let cmp;
                if (an !== null && bn !== null) {{
                    cmp = an - bn;
                }} else {{
                    cmp = av.localeCompare(bv, undefined, {{ sensitivity: 'base' }});
                }}
                return dir === 'asc' ? cmp : -cmp;
            }});
            rows.forEach(r => tbody.appendChild(r));
        }}
    </script>
</body>
</html>
"""

                html_file.write_text(html_content, encoding='utf-8')

    def generate_report(self, output_dir: str = './results/metadata_validation'):
        """Generate one consolidated CSV and one sortable HTML report."""
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        csv_file = Path(output_dir) / 'metadata_validation_report.csv'
        html_file = Path(output_dir) / 'metadata_validation_report.html'
        
        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'name', 'csv_file', 'csv_rows', 'csv_cols',
                'table', 'table_rows', 'table_cols',
                'rows_match', 'cols_match', 'status'
            ])
            writer.writeheader()
            writer.writerows(self.results)
        
        self._generate_html_report(html_file)

        logger.info(f"\nCSV report saved: {csv_file}")
        logger.info(f"HTML report saved: {html_file}")
        
        # Summary
        passed = sum(1 for r in self.results if r['status'] == 'PASSED')
        failed = sum(1 for r in self.results if r['status'] == 'FAILED')
        logger.info(f"\n{'='*80}")
        logger.info(f"SUMMARY: {passed} PASSED, {failed} FAILED")
        logger.info(f"{'='*80}")
        
        return csv_file, html_file


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Metadata-only validator: Compare row & column counts between CSV and Redshift tables'
    )
    parser.add_argument(
        '--config',
        required=True,
        help='Path to validation config YAML'
    )
    parser.add_argument(
        '--output-dir',
        default='./results/metadata_validation',
        help='Output directory for report (default: ./results/metadata_validation)'
    )
    
    args = parser.parse_args()
    
    logger.info(f"Loading config: {args.config}")
    validator = MetadataValidator(args.config)
    validator.validate_all()
    validator.generate_report(args.output_dir)


if __name__ == '__main__':
    main()
