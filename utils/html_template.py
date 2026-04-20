"""
HTML template generator for interactive validation reports.
Creates rich HTML reports with Chart.js visualizations and DataTables.
"""


def get_html_template() -> str:
    """
    Get the HTML template with embedded CSS and JavaScript.
    
    Returns:
        HTML template string with placeholders for data
    """
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{VALIDATION_NAME}} - Validation Report</title>
    
    <!-- DataTables CSS -->
    <link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">
    
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .header .subtitle {
            font-size: 1.1em;
            opacity: 0.9;
        }
        
        .summary-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            padding: 30px;
            background: #f8f9fa;
        }
        
        .card {
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 15px rgba(0,0,0,0.2);
        }
        
        .card-title {
            font-size: 0.9em;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }
        
        .card-value {
            font-size: 2.5em;
            font-weight: bold;
            color: #333;
        }
        
        .card.pass .card-value {
            color: #28a745;
        }
        
        .card.fail .card-value {
            color: #dc3545;
        }
        
        .card.info .card-value {
            color: #17a2b8;
        }
        
        .content {
            padding: 30px;
        }
        
        .section {
            margin-bottom: 40px;
        }
        
        .section-title {
            font-size: 1.8em;
            color: #333;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #667eea;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .section-title::before {
            content: '';
            width: 6px;
            height: 30px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 3px;
        }
        
        .chart-container {
            position: relative;
            height: 400px;
            margin: 20px 0;
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        .chart-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 30px;
            margin: 20px 0;
        }
        
        table.dataTable {
            width: 100% !important;
            border-collapse: collapse;
            margin: 20px 0;
            background: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        table.dataTable thead th {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.85em;
            letter-spacing: 0.5px;
        }
        
        table.dataTable tbody td {
            padding: 12px 15px;
            border-bottom: 1px solid #eee;
        }
        
        table.dataTable tbody tr:hover {
            background: #f8f9fa;
        }
        
        .badge {
            display: inline-block;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 600;
            text-transform: uppercase;
        }
        
        .badge.pass {
            background: #d4edda;
            color: #155724;
        }
        
        .badge.fail {
            background: #f8d7da;
            color: #721c24;
        }
        
        .badge.skip {
            background: #fff3cd;
            color: #856404;
        }
        
        .badge.info {
            background: #d1ecf1;
            color: #0c5460;
        }
        
        .metadata {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
            border-left: 4px solid #667eea;
        }
        
        .metadata-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 15px;
        }
        
        .metadata-item {
            display: flex;
            gap: 10px;
        }
        
        .metadata-label {
            font-weight: 600;
            color: #666;
            min-width: 120px;
        }
        
        .metadata-value {
            color: #333;
            word-break: break-all;
        }
        
        .collapsible {
            background: #667eea;
            color: white;
            cursor: pointer;
            padding: 15px;
            width: 100%;
            border: none;
            text-align: left;
            outline: none;
            font-size: 1.1em;
            font-weight: 600;
            border-radius: 8px;
            margin: 10px 0;
            transition: background 0.3s ease;
        }
        
        .collapsible:hover {
            background: #764ba2;
        }
        
        .collapsible::after {
            content: '\\25BC';
            float: right;
            margin-left: 5px;
            transition: transform 0.3s ease;
        }
        
        .collapsible.active::after {
            transform: rotate(-180deg);
        }
        
        .collapsible-content {
            max-height: 0;
            overflow: hidden;
            background: white;
            border-radius: 0 0 8px 8px;
        }
        
        .collapsible-content.active {
            max-height: none;
            padding: 20px;
            border: 2px solid #667eea;
            border-top: none;
        }
        
        .footer {
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            color: #666;
            border-top: 1px solid #dee2e6;
        }
        
        .timestamp {
            font-size: 0.9em;
            color: #999;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 {{VALIDATION_NAME}}</h1>
            <div class="subtitle">Data Validation Report</div>
            <div class="timestamp">Generated: {{TIMESTAMP}}</div>
        </div>
        
        <div class="summary-cards">
            <div class="card {{OVERALL_STATUS_CLASS}}">
                <div class="card-title">Overall Status</div>
                <div class="card-value">{{OVERALL_STATUS}}</div>
            </div>
            <div class="card pass">
                <div class="card-title">Passed Checks</div>
                <div class="card-value">{{PASS_COUNT}}</div>
            </div>
            <div class="card fail">
                <div class="card-title">Failed Checks</div>
                <div class="card-value">{{FAIL_COUNT}}</div>
            </div>
            <div class="card info">
                <div class="card-title">Total Checks</div>
                <div class="card-value">{{TOTAL_COUNT}}</div>
            </div>
        </div>
        
        <div class="content">
            <!-- Metadata Section -->
            <div class="section">
                <h2 class="section-title">Validation Configuration</h2>
                <div class="metadata">
                    <div class="metadata-grid">
                        {{METADATA_ITEMS}}
                    </div>
                </div>
            </div>
            
            <!-- Visualizations Section -->
            <div class="section">
                <h2 class="section-title">Validation Overview</h2>
                <div class="chart-grid">
                    <div class="chart-container">
                        <canvas id="statusChart"></canvas>
                    </div>
                    <div class="chart-container">
                        <canvas id="validationTypeChart"></canvas>
                    </div>
                </div>
            </div>
            
            <!-- Column-Level Analysis -->
            <div class="section">
                <h2 class="section-title">Column-Level Analysis</h2>
                <div class="chart-container" style="height: 500px;">
                    <canvas id="columnChart"></canvas>
                </div>
            </div>
            
            <!-- Detailed Results -->
            <div class="section">
                <h2 class="section-title">Detailed Results</h2>
                
                <!-- Failed Checks -->
                <button class="collapsible active">❌ Failed Checks ({{FAIL_COUNT}})</button>
                <div class="collapsible-content active">
                    <table id="failedTable" class="display">
                        <thead>
                            <tr>
                                <th>Validation Type</th>
                                <th>Column</th>
                                <th>Primary Key</th>
                                <th>Detail</th>
                                <th>Source Value</th>
                                <th>Target Value</th>
                            </tr>
                        </thead>
                        <tbody>
                            {{FAILED_ROWS}}
                        </tbody>
                    </table>
                </div>
                
                <!-- Passed Checks -->
                <button class="collapsible">✅ Passed Checks ({{PASS_COUNT}})</button>
                <div class="collapsible-content">
                    <table id="passedTable" class="display">
                        <thead>
                            <tr>
                                <th>Validation Type</th>
                                <th>Column</th>
                                <th>Detail</th>
                                <th>Source Value</th>
                                <th>Target Value</th>
                            </tr>
                        </thead>
                        <tbody>
                            {{PASSED_ROWS}}
                        </tbody>
                    </table>
                </div>
                
                <!-- All Results -->
                <button class="collapsible">📋 All Results ({{TOTAL_COUNT}})</button>
                <div class="collapsible-content">
                    <table id="allTable" class="display">
                        <thead>
                            <tr>
                                <th>Status</th>
                                <th>Validation Type</th>
                                <th>Column</th>
                                <th>Primary Key</th>
                                <th>Detail</th>
                                <th>Source Value</th>
                                <th>Target Value</th>
                            </tr>
                        </thead>
                        <tbody>
                            {{ALL_ROWS}}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        
        <div class="footer">
            <p>Universal Data Validation Framework v1.0</p>
            <p class="timestamp">Report generated on {{TIMESTAMP}}</p>
        </div>
    </div>
    
    <!-- jQuery -->
    <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
    
    <!-- DataTables -->
    <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
    
    <!-- Chart.js -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    
    <script>
        // Collapsible sections
        const collapsibles = document.querySelectorAll('.collapsible');
        collapsibles.forEach(coll => {
            coll.addEventListener('click', function() {
                this.classList.toggle('active');
                const content = this.nextElementSibling;
                content.classList.toggle('active');
            });
        });
        
        // Initialize DataTables
        $(document).ready(function() {
            $('#failedTable').DataTable({
                pageLength: 25,
                order: [[0, 'asc']],
                language: {
                    search: "Search failures:"
                }
            });
            
            $('#passedTable').DataTable({
                pageLength: 25,
                order: [[0, 'asc']],
                language: {
                    search: "Search passed:"
                }
            });
            
            $('#allTable').DataTable({
                pageLength: 50,
                order: [[0, 'asc']],
                language: {
                    search: "Search all:"
                }
            });
        });
        
        // Chart.js visualizations
        const chartData = {{CHART_DATA}};
        
        // Status Pie Chart
        new Chart(document.getElementById('statusChart'), {
            type: 'doughnut',
            data: {
                labels: ['Passed', 'Failed', 'Skipped'],
                datasets: [{
                    data: [chartData.pass_count, chartData.fail_count, chartData.skip_count],
                    backgroundColor: ['#28a745', '#dc3545', '#ffc107'],
                    borderWidth: 2,
                    borderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Validation Status Distribution',
                        font: { size: 16, weight: 'bold' }
                    },
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
        
        // Validation Type Bar Chart
        new Chart(document.getElementById('validationTypeChart'), {
            type: 'bar',
            data: {
                labels: chartData.validation_types,
                datasets: [{
                    label: 'Failed',
                    data: chartData.validation_fails,
                    backgroundColor: '#dc3545'
                }, {
                    label: 'Passed',
                    data: chartData.validation_passes,
                    backgroundColor: '#28a745'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Validation Type Breakdown',
                        font: { size: 16, weight: 'bold' }
                    },
                    legend: {
                        position: 'bottom'
                    }
                },
                scales: {
                    x: { stacked: true },
                    y: { stacked: true, beginAtZero: true }
                }
            }
        });
        
        // Column-Level Failures Chart
        if (chartData.column_failures.length > 0) {
            new Chart(document.getElementById('columnChart'), {
                type: 'bar',
                data: {
                    labels: chartData.column_names,
                    datasets: [{
                        label: 'Failures per Column',
                        data: chartData.column_failures,
                        backgroundColor: '#dc3545'
                    }]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        title: {
                            display: true,
                            text: 'Column-Level Failure Analysis (Top Culprits)',
                            font: { size: 16, weight: 'bold' }
                        },
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        x: { beginAtZero: true, title: { display: true, text: 'Number of Failures' } }
                    }
                }
            });
        }
    </script>
</body>
</html>
"""


def get_consolidated_html_template() -> str:
    """
    Get a tabbed HTML template for consolidated validation reports.
    Each validation gets its own tab.
    """
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Consolidated Validation Report</title>
    <link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body { font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif; background:linear-gradient(135deg,#667eea 0%,#764ba2 100%); padding:20px; min-height:100vh; }
        .container { max-width:1400px; margin:0 auto; background:white; border-radius:12px; box-shadow:0 10px 40px rgba(0,0,0,0.2); overflow:hidden; }
        .header { background:linear-gradient(135deg,#667eea 0%,#764ba2 100%); color:white; padding:30px; text-align:center; }
        .header h1 { font-size:2.5em; margin-bottom:10px; text-shadow:2px 2px 4px rgba(0,0,0,0.3); }
        .header .subtitle { font-size:1.1em; opacity:0.9; }
        .summary-cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:20px; padding:30px; background:#f8f9fa; }
        .card { background:white; padding:25px; border-radius:10px; box-shadow:0 4px 6px rgba(0,0,0,0.1); transition:transform 0.3s ease,box-shadow 0.3s ease; }
        .card:hover { transform:translateY(-5px); box-shadow:0 8px 15px rgba(0,0,0,0.2); }
        .card-title { font-size:0.9em; color:#666; text-transform:uppercase; letter-spacing:1px; margin-bottom:10px; }
        .card-value { font-size:2.5em; font-weight:bold; color:#333; }
        .card.pass .card-value { color:#28a745; }
        .card.fail .card-value { color:#dc3545; }
        .card.info .card-value { color:#17a2b8; }
        .content { padding:30px; }
        .section { margin-bottom:40px; }
        .section-title { font-size:1.8em; color:#333; margin-bottom:20px; padding-bottom:10px; border-bottom:3px solid #667eea; display:flex; align-items:center; gap:10px; }
        .section-title::before { content:''; width:6px; height:30px; background:linear-gradient(135deg,#667eea 0%,#764ba2 100%); border-radius:3px; }
        .chart-container { position:relative; height:400px; margin:20px 0; background:white; padding:20px; border-radius:10px; box-shadow:0 2px 8px rgba(0,0,0,0.1); }
        .chart-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(400px,1fr)); gap:30px; margin:20px 0; }
        table.dataTable { width:100%!important; border-collapse:collapse; margin:20px 0; background:white; border-radius:10px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.1); }
        table.dataTable thead th { background:linear-gradient(135deg,#667eea 0%,#764ba2 100%); color:white; padding:15px; text-align:left; font-weight:600; text-transform:uppercase; font-size:0.85em; letter-spacing:0.5px; }
        table.dataTable tbody td { padding:12px 15px; border-bottom:1px solid #eee; }
        table.dataTable tbody tr:hover { background:#f8f9fa; }
        .badge { display:inline-block; padding:5px 12px; border-radius:20px; font-size:0.85em; font-weight:600; text-transform:uppercase; }
        .badge.pass { background:#d4edda; color:#155724; }
        .badge.fail { background:#f8d7da; color:#721c24; }
        .badge.skip { background:#fff3cd; color:#856404; }
        .metadata { background:#f8f9fa; padding:20px; border-radius:10px; margin:20px 0; border-left:4px solid #667eea; }
        .metadata-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:15px; }
        .metadata-item { display:flex; gap:10px; }
        .metadata-label { font-weight:600; color:#666; min-width:120px; }
        .metadata-value { color:#333; word-break:break-all; }
        .collapsible { background:#667eea; color:white; cursor:pointer; padding:15px; width:100%; border:none; text-align:left; outline:none; font-size:1.1em; font-weight:600; border-radius:8px; margin:10px 0; transition:background 0.3s ease; }
        .collapsible:hover { background:#764ba2; }
        .collapsible::after { content:'\\25BC'; float:right; margin-left:5px; transition:transform 0.3s ease; }
        .collapsible.active::after { transform:rotate(-180deg); }
        .collapsible-content { max-height:0; overflow:hidden; background:white; border-radius:0 0 8px 8px; }
        .collapsible-content.active { max-height:none; padding:20px; border:2px solid #667eea; border-top:none; }
        .footer { background:#f8f9fa; padding:20px; text-align:center; color:#666; border-top:1px solid #dee2e6; }
        .timestamp { font-size:0.9em; color:#999; }

        /* Tab styles */
        .tab-bar { display:flex; flex-wrap:wrap; gap:4px; padding:10px 30px 0; background:#f8f9fa; border-bottom:2px solid #667eea; overflow-x:auto; }
        .tab-btn { padding:10px 20px; border:none; background:#e0e0e0; color:#333; font-size:0.95em; font-weight:600; cursor:pointer; border-radius:8px 8px 0 0; transition:background 0.2s; white-space:nowrap; }
        .tab-btn:hover { background:#c8c8f0; }
        .tab-btn.active { background:#667eea; color:white; }
        .tab-content { display:none; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Consolidated Validation Report</h1>
            <div class="subtitle">{{PASSED_VALIDATIONS}}/{{TOTAL_VALIDATIONS}} validations passed</div>
            <div class="timestamp">Generated: {{TIMESTAMP}}</div>
        </div>

        <div class="tab-bar">
            {{TAB_HEADERS}}
        </div>

        {{TAB_CONTENTS}}

        <div class="footer">
            <p>Universal Data Validation Framework v1.0</p>
            <p class="timestamp">Report generated on {{TIMESTAMP}}</p>
        </div>
    </div>

    <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <script>
        // Tab switching
        document.querySelectorAll('.tab-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
                this.classList.add('active');
                var tabId = this.getAttribute('data-tab');
                document.getElementById(tabId).style.display = 'block';
                // Lazy-init charts/tables for this tab
                if (window._tabInits && window._tabInits[tabId]) {
                    window._tabInits[tabId]();
                    delete window._tabInits[tabId];
                }
            });
        });

        // Collapsible sections
        document.addEventListener('click', function(e) {
            if (e.target.classList.contains('collapsible')) {
                e.target.classList.toggle('active');
                e.target.nextElementSibling.classList.toggle('active');
            }
        });
    </script>
</body>
</html>
"""
