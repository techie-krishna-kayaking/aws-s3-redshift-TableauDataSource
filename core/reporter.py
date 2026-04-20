"""
Report generator for validation results.
Creates CSV and interactive HTML reports with visualizations.
"""
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
import json
import logging
import csv

from utils.html_template import get_html_template, get_consolidated_html_template
from utils.helpers import safe_repr

logger = logging.getLogger(__name__)


class Reporter:
    """
    Report generator for validation results.
    
    Generates:
    - CSV reports (machine-readable)
    - Interactive HTML reports with visualizations
    """
    
    def __init__(self, validation_name: str, results: List[Dict[str, Any]],
                 source_metadata: Dict[str, Any], target_metadata: Dict[str, Any]):
        """
        Initialize reporter.
        
        Args:
            validation_name: Name of the validation
            results: List of validation result dictionaries
            source_metadata: Metadata about source
            target_metadata: Metadata about target
        """
        self.validation_name = validation_name
        self.results = results
        self.source_metadata = source_metadata
        self.target_metadata = target_metadata
        self.results_df = pd.DataFrame(results)
    
    def generate_csv(self, output_path: Path) -> Path:
        """
        Generate CSV report.
        
        Args:
            output_path: Path to save CSV file
        
        Returns:
            Path to generated CSV file
        """
        logger.info(f"Generating CSV report: {output_path}")
        
        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save to CSV
        self.results_df.to_csv(output_path, index=False, quoting=csv.QUOTE_MINIMAL)
        
        logger.info(f"CSV report saved: {output_path}")
        return output_path
    
    def generate_html(self, output_path: Path) -> Path:
        """
        Generate interactive HTML report.
        
        Args:
            output_path: Path to save HTML file
        
        Returns:
            Path to generated HTML file
        """
        logger.info(f"Generating HTML report: {output_path}")
        
        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Get template
        template = get_html_template()
        
        # Calculate statistics
        stats = self._calculate_statistics()
        
        # Generate chart data
        chart_data = self._generate_chart_data()
        
        # Generate metadata HTML
        metadata_html = self._generate_metadata_html()
        
        # Generate table rows
        failed_rows = self._generate_table_rows(self.results_df[self.results_df['result'] == 'FAIL'])
        passed_rows = self._generate_table_rows(self.results_df[self.results_df['result'] == 'PASS'], include_pk=False)
        all_rows = self._generate_table_rows(self.results_df, include_status=True)
        
        # Replace placeholders
        html = template.replace('{{VALIDATION_NAME}}', self.validation_name)
        html = html.replace('{{TIMESTAMP}}', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        html = html.replace('{{OVERALL_STATUS}}', stats['overall_status'])
        html = html.replace('{{OVERALL_STATUS_CLASS}}', stats['overall_status_class'])
        html = html.replace('{{PASS_COUNT}}', str(stats['pass_count']))
        html = html.replace('{{FAIL_COUNT}}', str(stats['fail_count']))
        html = html.replace('{{TOTAL_COUNT}}', str(stats['total_count']))
        html = html.replace('{{METADATA_ITEMS}}', metadata_html)
        html = html.replace('{{CHART_DATA}}', json.dumps(chart_data))
        html = html.replace('{{FAILED_ROWS}}', failed_rows)
        html = html.replace('{{PASSED_ROWS}}', passed_rows)
        html = html.replace('{{ALL_ROWS}}', all_rows)
        
        # Save HTML
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        logger.info(f"HTML report saved: {output_path}")
        return output_path
    
    def _calculate_statistics(self) -> Dict[str, Any]:
        """Calculate summary statistics."""
        pass_count = len(self.results_df[self.results_df['result'] == 'PASS'])
        fail_count = len(self.results_df[self.results_df['result'] == 'FAIL'])
        skip_count = len(self.results_df[self.results_df['result'] == 'SKIP'])
        total_count = len(self.results_df)
        
        overall_status = '✅ PASS' if fail_count == 0 else '❌ FAIL'
        overall_status_class = 'pass' if fail_count == 0 else 'fail'
        
        return {
            'pass_count': pass_count,
            'fail_count': fail_count,
            'skip_count': skip_count,
            'total_count': total_count,
            'overall_status': overall_status,
            'overall_status_class': overall_status_class
        }
    
    def _generate_chart_data(self) -> Dict[str, Any]:
        """Generate data for Chart.js visualizations."""
        stats = self._calculate_statistics()
        
        # Validation type breakdown
        validation_types = self.results_df['validation'].unique()
        validation_fails = []
        validation_passes = []
        
        for vtype in validation_types:
            vtype_df = self.results_df[self.results_df['validation'] == vtype]
            validation_fails.append(int(len(vtype_df[vtype_df['result'] == 'FAIL'])))
            validation_passes.append(int(len(vtype_df[vtype_df['result'] == 'PASS'])))
        
        # Column-level failures (top 20 culprits)
        failed_df = self.results_df[self.results_df['result'] == 'FAIL']
        column_failures = failed_df[failed_df['column'] != ''].groupby('column').size()
        column_failures = column_failures.sort_values(ascending=False).head(20)
        
        return {
            'pass_count': int(stats['pass_count']),
            'fail_count': int(stats['fail_count']),
            'skip_count': int(stats['skip_count']),
            'validation_types': [str(v) for v in validation_types],
            'validation_fails': validation_fails,
            'validation_passes': validation_passes,
            'column_names': [str(c) for c in column_failures.index] if len(column_failures) > 0 else [],
            'column_failures': [int(v) for v in column_failures.values] if len(column_failures) > 0 else []
        }

    
    def _generate_metadata_html(self) -> str:
        """Generate HTML for metadata section."""
        items = []
        
        # Source metadata
        items.append(f'''
            <div class="metadata-item">
                <div class="metadata-label">Source Type:</div>
                <div class="metadata-value">{self.source_metadata.get('source_type', 'Unknown')}</div>
            </div>
        ''')
        
        items.append(f'''
            <div class="metadata-item">
                <div class="metadata-label">Source Path:</div>
                <div class="metadata-value">{self.source_metadata.get('source_path', 'Unknown')}</div>
            </div>
        ''')
        
        items.append(f'''
            <div class="metadata-item">
                <div class="metadata-label">Source Rows:</div>
                <div class="metadata-value">{self.source_metadata.get('row_count', 'N/A')}</div>
            </div>
        ''')
        
        items.append(f'''
            <div class="metadata-item">
                <div class="metadata-label">Source Columns:</div>
                <div class="metadata-value">{self.source_metadata.get('column_count', 'N/A')}</div>
            </div>
        ''')
        
        # Target metadata
        items.append(f'''
            <div class="metadata-item">
                <div class="metadata-label">Target Type:</div>
                <div class="metadata-value">{self.target_metadata.get('source_type', 'Unknown')}</div>
            </div>
        ''')
        
        items.append(f'''
            <div class="metadata-item">
                <div class="metadata-label">Target Path:</div>
                <div class="metadata-value">{self.target_metadata.get('source_path', 'Unknown')}</div>
            </div>
        ''')
        
        items.append(f'''
            <div class="metadata-item">
                <div class="metadata-label">Target Rows:</div>
                <div class="metadata-value">{self.target_metadata.get('row_count', 'N/A')}</div>
            </div>
        ''')
        
        items.append(f'''
            <div class="metadata-item">
                <div class="metadata-label">Target Columns:</div>
                <div class="metadata-value">{self.target_metadata.get('column_count', 'N/A')}</div>
            </div>
        ''')
        
        return '\n'.join(items)
    
    def _generate_table_rows(self, df: pd.DataFrame, include_status: bool = False, 
                            include_pk: bool = True) -> str:
        """Generate HTML table rows from DataFrame."""
        if len(df) == 0:
            return '<tr><td colspan="6">No results</td></tr>'
        
        rows = []
        for _, row in df.iterrows():
            # Create badge for status if needed
            if include_status:
                status_class = row['result'].lower()
                status_badge = f'<span class="badge {status_class}">{row["result"]}</span>'
                status_cell = f'<td>{status_badge}</td>'
            else:
                status_cell = ''
            
            # Format values
            validation = row['validation'].replace('_', ' ').title()
            column = row['column'] if row['column'] else '-'
            pk = row['pk'] if (include_pk and row['pk']) else '-'
            detail = row['detail']
            source_val = safe_repr(row['source_value'], 50) if row['source_value'] else '-'
            target_val = safe_repr(row['target_value'], 50) if row['target_value'] else '-'
            
            # Build row
            if include_pk:
                row_html = f'''
                    <tr>
                        {status_cell}
                        <td>{validation}</td>
                        <td>{column}</td>
                        <td>{pk}</td>
                        <td>{detail}</td>
                        <td>{source_val}</td>
                        <td>{target_val}</td>
                    </tr>
                '''
            else:
                row_html = f'''
                    <tr>
                        {status_cell}
                        <td>{validation}</td>
                        <td>{column}</td>
                        <td>{detail}</td>
                        <td>{source_val}</td>
                        <td>{target_val}</td>
                    </tr>
                '''
            
            rows.append(row_html)
        
        return '\n'.join(rows)
    
    def generate_reports(self, output_dir: Path, base_name: str = None) -> Dict[str, Path]:
        """
        Generate both CSV and HTML reports with timestamp.
        
        Args:
            output_dir: Directory to save reports
            base_name: Base name for files (defaults to validation_name)
        
        Returns:
            Dictionary with paths to generated reports
        """
        if base_name is None:
            # Sanitize validation name for filename
            base_name = self.validation_name.lower().replace(' ', '_').replace('/', '_')
        
        # Add timestamp to filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_path = output_dir / f"{base_name}_{timestamp}.csv"
        html_path = output_dir / f"{base_name}_{timestamp}.html"
        
        return {
            'csv': self.generate_csv(csv_path),
            'html': self.generate_html(html_path)
        }


class ConsolidatedReporter:
    """
    Generates a single consolidated Excel workbook and a single tabbed HTML report
    from multiple validation results.
    """

    def __init__(self, all_results: List[Dict[str, Any]]):
        """
        Args:
            all_results: List of result dicts returned by Validator.run()
        """
        self.all_results = all_results

    def generate_excel(self, output_path: Path) -> Path:
        """Generate a single Excel file with one sheet per validation."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Summary sheet
            summary_rows = []
            for r in self.all_results:
                summary_rows.append({
                    'Validation': r['name'],
                    'Status': r['status'],
                    'Passed': r['pass_count'],
                    'Failed': r['fail_count'],
                    'Total': r['total_count'],
                })
            pd.DataFrame(summary_rows).to_excel(writer, sheet_name='Summary', index=False)

            for r in self.all_results:
                sheet_name = r['name'][:31]  # Excel sheet name limit
                df = pd.DataFrame(r['results'])
                df.to_excel(writer, sheet_name=sheet_name, index=False)

        logger.info(f"Consolidated Excel saved: {output_path}")
        return output_path

    def generate_html(self, output_path: Path) -> Path:
        """Generate a single HTML file with tabs for each validation."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build tab headers and tab content
        tab_headers = []
        tab_contents = []

        for idx, r in enumerate(self.all_results):
            name = r['name']
            status_icon = '✅' if r['status'] == 'PASS' else '❌'
            active = 'active' if idx == 0 else ''
            tab_headers.append(
                f'<button class="tab-btn {active}" data-tab="tab-{idx}">{status_icon} {name}</button>'
            )

            reporter = Reporter(
                validation_name=name,
                results=r['results'],
                source_metadata=r.get('source_metadata', {}),
                target_metadata=r.get('target_metadata', {}),
            )
            stats = reporter._calculate_statistics()
            chart_data = reporter._generate_chart_data()
            metadata_html = reporter._generate_metadata_html()
            failed_rows = reporter._generate_table_rows(
                reporter.results_df[reporter.results_df['result'] == 'FAIL'])
            passed_rows = reporter._generate_table_rows(
                reporter.results_df[reporter.results_df['result'] == 'PASS'], include_pk=False)
            all_rows = reporter._generate_table_rows(reporter.results_df, include_status=True)

            display = 'block' if idx == 0 else 'none'
            tab_contents.append(f'''
            <div class="tab-content" id="tab-{idx}" style="display:{display}">
                <div class="summary-cards">
                    <div class="card {stats['overall_status_class']}">
                        <div class="card-title">Overall Status</div>
                        <div class="card-value">{stats['overall_status']}</div>
                    </div>
                    <div class="card pass">
                        <div class="card-title">Passed Checks</div>
                        <div class="card-value">{stats['pass_count']}</div>
                    </div>
                    <div class="card fail">
                        <div class="card-title">Failed Checks</div>
                        <div class="card-value">{stats['fail_count']}</div>
                    </div>
                    <div class="card info">
                        <div class="card-title">Total Checks</div>
                        <div class="card-value">{stats['total_count']}</div>
                    </div>
                </div>
                <div class="content">
                    <div class="section">
                        <h2 class="section-title">Validation Configuration</h2>
                        <div class="metadata"><div class="metadata-grid">{metadata_html}</div></div>
                    </div>
                    <div class="section">
                        <h2 class="section-title">Validation Overview</h2>
                        <div class="chart-grid">
                            <div class="chart-container"><canvas id="statusChart-{idx}"></canvas></div>
                            <div class="chart-container"><canvas id="validationTypeChart-{idx}"></canvas></div>
                        </div>
                    </div>
                    <div class="section">
                        <h2 class="section-title">Column-Level Analysis</h2>
                        <div class="chart-container" style="height:500px;"><canvas id="columnChart-{idx}"></canvas></div>
                    </div>
                    <div class="section">
                        <h2 class="section-title">Detailed Results</h2>
                        <button class="collapsible active">❌ Failed Checks ({stats['fail_count']})</button>
                        <div class="collapsible-content active">
                            <table id="failedTable-{idx}" class="display">
                                <thead><tr><th>Validation Type</th><th>Column</th><th>Primary Key</th><th>Detail</th><th>Source Value</th><th>Target Value</th></tr></thead>
                                <tbody>{failed_rows}</tbody>
                            </table>
                        </div>
                        <button class="collapsible">✅ Passed Checks ({stats['pass_count']})</button>
                        <div class="collapsible-content">
                            <table id="passedTable-{idx}" class="display">
                                <thead><tr><th>Validation Type</th><th>Column</th><th>Detail</th><th>Source Value</th><th>Target Value</th></tr></thead>
                                <tbody>{passed_rows}</tbody>
                            </table>
                        </div>
                        <button class="collapsible">📋 All Results ({stats['total_count']})</button>
                        <div class="collapsible-content">
                            <table id="allTable-{idx}" class="display">
                                <thead><tr><th>Status</th><th>Validation Type</th><th>Column</th><th>Primary Key</th><th>Detail</th><th>Source Value</th><th>Target Value</th></tr></thead>
                                <tbody>{all_rows}</tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
            <script>
            (function() {{
                const cd = {json.dumps(chart_data)};
                function initCharts_{idx}() {{
                    new Chart(document.getElementById('statusChart-{idx}'), {{
                        type:'doughnut', data:{{ labels:['Passed','Failed','Skipped'], datasets:[{{ data:[cd.pass_count,cd.fail_count,cd.skip_count], backgroundColor:['#28a745','#dc3545','#ffc107'], borderWidth:2, borderColor:'#fff' }}] }},
                        options:{{ responsive:true, maintainAspectRatio:false, plugins:{{ title:{{ display:true, text:'Validation Status Distribution', font:{{size:16,weight:'bold'}} }}, legend:{{position:'bottom'}} }} }}
                    }});
                    new Chart(document.getElementById('validationTypeChart-{idx}'), {{
                        type:'bar', data:{{ labels:cd.validation_types, datasets:[{{ label:'Failed', data:cd.validation_fails, backgroundColor:'#dc3545' }},{{ label:'Passed', data:cd.validation_passes, backgroundColor:'#28a745' }}] }},
                        options:{{ responsive:true, maintainAspectRatio:false, plugins:{{ title:{{ display:true, text:'Validation Type Breakdown', font:{{size:16,weight:'bold'}} }}, legend:{{position:'bottom'}} }}, scales:{{ x:{{stacked:true}}, y:{{stacked:true,beginAtZero:true}} }} }}
                    }});
                    if (cd.column_failures.length > 0) {{
                        new Chart(document.getElementById('columnChart-{idx}'), {{
                            type:'bar', data:{{ labels:cd.column_names, datasets:[{{ label:'Failures per Column', data:cd.column_failures, backgroundColor:'#dc3545' }}] }},
                            options:{{ indexAxis:'y', responsive:true, maintainAspectRatio:false, plugins:{{ title:{{ display:true, text:'Column-Level Failure Analysis', font:{{size:16,weight:'bold'}} }}, legend:{{display:false}} }}, scales:{{ x:{{beginAtZero:true}} }} }}
                        }});
                    }}
                    $('#failedTable-{idx}').DataTable({{ pageLength:25, order:[[0,'asc']], language:{{search:"Search failures:"}} }});
                    $('#passedTable-{idx}').DataTable({{ pageLength:25, order:[[0,'asc']], language:{{search:"Search passed:"}} }});
                    $('#allTable-{idx}').DataTable({{ pageLength:50, order:[[0,'asc']], language:{{search:"Search all:"}} }});
                }}
                window._tabInits = window._tabInits || {{}};
                window._tabInits['tab-{idx}'] = initCharts_{idx};
                {'initCharts_' + str(idx) + '();' if idx == 0 else ''}
            }})();
            </script>
            ''')

        # Build overall summary
        total_v = len(self.all_results)
        passed_v = sum(1 for r in self.all_results if r['status'] == 'PASS')
        failed_v = total_v - passed_v

        template = get_consolidated_html_template()
        html = template.replace('{{TIMESTAMP}}', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        html = html.replace('{{TOTAL_VALIDATIONS}}', str(total_v))
        html = html.replace('{{PASSED_VALIDATIONS}}', str(passed_v))
        html = html.replace('{{FAILED_VALIDATIONS}}', str(failed_v))
        html = html.replace('{{TAB_HEADERS}}', '\n'.join(tab_headers))
        html = html.replace('{{TAB_CONTENTS}}', '\n'.join(tab_contents))

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        logger.info(f"Consolidated HTML saved: {output_path}")
        return output_path

    def generate_reports(self, output_dir: Path, base_name: str = 'consolidated') -> Dict[str, Path]:
        """Generate consolidated Excel + tabbed HTML."""
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        excel_path = output_dir / f"{base_name}_{timestamp}.xlsx"
        html_path = output_dir / f"{base_name}_{timestamp}.html"

        return {
            'excel': self.generate_excel(excel_path),
            'html': self.generate_html(html_path),
        }
