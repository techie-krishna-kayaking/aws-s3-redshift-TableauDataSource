"""
performance_reporter.py — Generates HTML report + CSV for performance test results.

Outputs:
  • Self-contained HTML report (dark-themed, matching existing report style)
  • Single CSV file with all iteration data (collated)
"""
from __future__ import annotations

import base64
import csv
from datetime import datetime
from pathlib import Path
from typing import List

from jinja2 import Template

from bi_regression.config_parser import TestConfig
from bi_regression.performance_tester import PerfDashboardResult


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

_PERF_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Performance Test Report — {{ run_date }}</title>
  <style>
    :root {
      --bg:        #0f1117;
      --surface:   #1a1d27;
      --card:      #22253a;
      --border:    #2e3150;
      --accent:    #5b6af0;
      --pass:      #22c55e;
      --fail:      #ef4444;
      --warn:      #f59e0b;
      --text:      #e2e8f0;
      --muted:     #94a3b8;
      --radius:    12px;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; font-size: 14px; }

    .header {
      background: linear-gradient(135deg, #1e2240 0%, #0f1117 100%);
      border-bottom: 1px solid var(--border);
      padding: 32px 40px;
    }
    .header h1 { font-size: 28px; font-weight: 700; letter-spacing: -0.5px; }
    .header h1 span { color: var(--accent); }
    .header .type-badge {
      display: inline-block; margin-left: 16px;
      font-size: 12px; font-weight: 700; padding: 4px 14px;
      border-radius: 20px; text-transform: uppercase; letter-spacing: 1.5px;
      background: rgba(91,106,240,0.2); color: var(--accent); border: 1px solid var(--accent);
      vertical-align: middle;
    }
    .meta { color: var(--muted); font-size: 13px; margin-top: 6px; }

    .summary { display: flex; gap: 16px; padding: 24px 40px; flex-wrap: wrap; }
    .stat-card {
      background: var(--card); border: 1px solid var(--border);
      border-radius: var(--radius); padding: 20px 28px; min-width: 150px; flex: 1;
    }
    .stat-card .label { font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: var(--muted); }
    .stat-card .value { font-size: 36px; font-weight: 700; margin-top: 6px; }
    .stat-card.pass .value { color: var(--pass); }
    .stat-card.fail .value { color: var(--fail); }
    .stat-card.total .value { color: var(--accent); }

    .section { padding: 0 40px 40px; }
    .section h2 { font-size: 18px; font-weight: 600; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 1px solid var(--border); }

    .results { display: flex; flex-direction: column; gap: 24px; }

    .result-card {
      background: var(--card); border: 1px solid var(--border);
      border-radius: var(--radius); overflow: hidden;
    }
    .result-card.pass { border-left: 4px solid var(--pass); }
    .result-card.fail { border-left: 4px solid var(--fail); }

    .card-header {
      display: flex; align-items: center; gap: 16px;
      padding: 16px 20px; cursor: pointer; user-select: none;
    }
    .card-header:hover { background: rgba(255,255,255,0.03); }
    .badge {
      font-size: 11px; font-weight: 700; padding: 3px 10px;
      border-radius: 20px; text-transform: uppercase; letter-spacing: 1px;
    }
    .badge.pass { background: rgba(34,197,94,0.15); color: var(--pass); border: 1px solid var(--pass); }
    .badge.fail { background: rgba(239,68,68,0.15); color: var(--fail); border: 1px solid var(--fail); }
    .dash-name { font-size: 15px; font-weight: 600; flex: 1; }
    .dash-url { font-size: 12px; color: var(--muted); max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .arrow { color: var(--muted); font-size: 18px; transition: transform 0.2s; }
    .card-header.open .arrow { transform: rotate(90deg); }

    .card-body { display: none; padding: 0 20px 20px; }
    .card-body.open { display: block; }

    /* Metrics grid */
    .metrics-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 16px; }
    .metric-box {
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 8px; padding: 16px;
    }
    .metric-box h4 {
      font-size: 13px; font-weight: 600; margin-bottom: 12px;
      display: flex; align-items: center; gap: 8px;
    }
    .metric-box h4 .metric-badge {
      font-size: 10px; font-weight: 700; padding: 2px 8px;
      border-radius: 10px; text-transform: uppercase;
    }
    .metric-badge.pass { background: rgba(34,197,94,0.15); color: var(--pass); }
    .metric-badge.fail { background: rgba(239,68,68,0.15); color: var(--fail); }

    .metric-stats { display: flex; gap: 20px; flex-wrap: wrap; }
    .metric-stat { text-align: center; }
    .metric-stat .ms-label { font-size: 10px; text-transform: uppercase; letter-spacing: 1px; color: var(--muted); }
    .metric-stat .ms-value { font-size: 22px; font-weight: 700; margin-top: 2px; }
    .metric-stat .ms-value.pass-color { color: var(--pass); }
    .metric-stat .ms-value.fail-color { color: var(--fail); }
    .metric-stat .ms-value.accent-color { color: var(--accent); }

    .threshold-line { margin-top: 10px; font-size: 12px; color: var(--muted); }
    .threshold-line strong { color: var(--text); }

    /* Iteration table */
    .iter-table { width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 13px; }
    .iter-table th {
      text-align: left; padding: 8px 12px;
      background: rgba(255,255,255,0.05);
      color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 1px;
    }
    .iter-table td { padding: 8px 12px; border-top: 1px solid var(--border); }
    .iter-table tr:hover td { background: rgba(255,255,255,0.02); }
    .iter-table .ms { font-family: monospace; font-weight: 600; }

    /* Screenshot */
    .screenshot-section { margin-top: 20px; }
    .screenshot-section .ss-label {
      font-size: 11px; text-transform: uppercase; letter-spacing: 1px;
      color: var(--muted); margin-bottom: 8px;
    }
    .screenshot-section img {
      width: 100%; border-radius: 8px; border: 1px solid var(--border); cursor: pointer;
    }
    .screenshot-section img:hover { border-color: var(--accent); }

    /* Bar chart */
    .bar-chart { display: flex; align-items: flex-end; gap: 6px; height: 120px; margin-top: 16px; padding: 0 4px; }
    .bar-group { display: flex; flex-direction: column; align-items: center; flex: 1; gap: 4px; }
    .bar {
      width: 100%; min-width: 20px; border-radius: 4px 4px 0 0;
      transition: height 0.3s;
    }
    .bar.render { background: var(--accent); }
    .bar.interaction { background: var(--warn); }
    .bar-label { font-size: 10px; color: var(--muted); }
    .bar-chart-legend { display: flex; gap: 16px; margin-top: 8px; font-size: 11px; color: var(--muted); }
    .bar-chart-legend .dot { width: 10px; height: 10px; border-radius: 2px; display: inline-block; margin-right: 4px; }

    /* Lightbox */
    .lightbox { display:none; position:fixed; z-index:1000; top:0; left:0; width:100vw; height:100vh;
      background:rgba(0,0,0,0.92); justify-content:center; align-items:center; cursor:zoom-out; }
    .lightbox.show { display:flex; }
    .lightbox img { max-width:95vw; max-height:95vh; border-radius:8px; }

    .footer { text-align: center; color: var(--muted); font-size: 12px; padding: 24px; border-top: 1px solid var(--border); margin-top: 20px; }
  </style>
</head>
<body>

<div class="header">
  <h1>Tableau <span>Performance Test</span> Report <span class="type-badge">PERFORMANCE TESTING</span></h1>
  <p class="meta">
    Run Date: {{ run_date }}
    &nbsp;|&nbsp; Iterations per dashboard: <strong>{{ iterations }}</strong>
    &nbsp;|&nbsp; Output: {{ run_dir }}
  </p>
</div>

<div class="summary">
  <div class="stat-card total">
    <div class="label">Dashboards Tested</div>
    <div class="value">{{ total }}</div>
  </div>
  <div class="stat-card pass">
    <div class="label">Passed</div>
    <div class="value">{{ passed }}</div>
  </div>
  <div class="stat-card fail">
    <div class="label">Failed</div>
    <div class="value">{{ failed }}</div>
  </div>
  <div class="stat-card total">
    <div class="label">Iterations</div>
    <div class="value">{{ iterations }}</div>
  </div>
</div>

<div class="section">
  <h2>Dashboard Results</h2>
  <div class="results">
    {% for r in results %}
    <div class="result-card {{ 'pass' if r.passed else 'fail' }}">
      <div class="card-header" onclick="toggle(this)">
        <span class="badge {{ 'pass' if r.passed else 'fail' }}">{{ 'PASS' if r.passed else 'FAIL' }}</span>
        <span class="dash-name">{{ r.label }}</span>
        <span class="dash-url" title="{{ r.url }}">{{ r.url }}</span>
        <span class="arrow">▶</span>
      </div>
      <div class="card-body">

        <!-- Metrics summary -->
        <div class="metrics-grid">
          <div class="metric-box">
            <h4>First Render Time
              <span class="metric-badge {{ 'pass' if r.first_render_passed else 'fail' }}">
                {{ 'PASS' if r.first_render_passed else 'FAIL' }}
              </span>
            </h4>
            <div class="metric-stats">
              <div class="metric-stat">
                <div class="ms-label">Min</div>
                <div class="ms-value accent-color">{{ "%.0f"|format(r.first_render_min) }}<small>ms</small></div>
              </div>
              <div class="metric-stat">
                <div class="ms-label">Avg</div>
                <div class="ms-value {{ 'pass-color' if r.first_render_passed else 'fail-color' }}">{{ "%.0f"|format(r.first_render_avg) }}<small>ms</small></div>
              </div>
              <div class="metric-stat">
                <div class="ms-label">Max</div>
                <div class="ms-value accent-color">{{ "%.0f"|format(r.first_render_max) }}<small>ms</small></div>
              </div>
            </div>
            <div class="threshold-line">Threshold: <strong>{{ "%.0f"|format(r.first_render_threshold) }} ms</strong></div>
          </div>

          <div class="metric-box">
            <h4>Interaction Time
              <span class="metric-badge {{ 'pass' if r.interaction_passed else 'fail' }}">
                {{ 'PASS' if r.interaction_passed else 'FAIL' }}
              </span>
            </h4>
            <div class="metric-stats">
              <div class="metric-stat">
                <div class="ms-label">Min</div>
                <div class="ms-value accent-color">{{ "%.0f"|format(r.interaction_min) }}<small>ms</small></div>
              </div>
              <div class="metric-stat">
                <div class="ms-label">Avg</div>
                <div class="ms-value {{ 'pass-color' if r.interaction_passed else 'fail-color' }}">{{ "%.0f"|format(r.interaction_avg) }}<small>ms</small></div>
              </div>
              <div class="metric-stat">
                <div class="ms-label">Max</div>
                <div class="ms-value accent-color">{{ "%.0f"|format(r.interaction_max) }}<small>ms</small></div>
              </div>
            </div>
            <div class="threshold-line">Threshold: <strong>{{ "%.0f"|format(r.interaction_threshold) }} ms</strong></div>
          </div>
        </div>

        <!-- Bar chart of iterations -->
        {% if r.iterations %}
        <h4 style="margin-top:20px; font-size:13px; color:var(--muted);">Iteration Timings</h4>
        <div class="bar-chart">
          {% set max_ms = r.chart_max %}
          {% for it in r.iterations %}
          <div class="bar-group">
            {% if max_ms > 0 %}
            <div class="bar render" style="height: {{ (it.first_render_ms / max_ms * 100)|int }}%;" title="Render: {{ '%.0f'|format(it.first_render_ms) }}ms"></div>
            {% endif %}
            <div class="bar-label">#{{ it.iteration }}</div>
          </div>
          {% endfor %}
        </div>
        <div class="bar-chart-legend">
          <span><span class="dot" style="background:var(--accent);"></span> First Render</span>
          <span><span class="dot" style="background:var(--warn);"></span> Interaction</span>
        </div>
        {% endif %}

        <!-- Iteration details table -->
        <table class="iter-table">
          <thead>
            <tr>
              <th>Iteration</th>
              <th>First Render (ms)</th>
              <th>Interaction (ms)</th>
            </tr>
          </thead>
          <tbody>
            {% for it in r.iterations %}
            <tr>
              <td>{{ it.iteration }}</td>
              <td class="ms">{{ "%.0f"|format(it.first_render_ms) if it.first_render_ms >= 0 else 'ERROR' }}</td>
              <td class="ms">{{ "%.0f"|format(it.interaction_ms) if it.interaction_ms >= 0 else 'ERROR' }}</td>
            </tr>
            {% endfor %}
          </tbody>
        </table>

        {% if r.screenshot_b64 %}
        <div class="screenshot-section">
          <div class="ss-label">Dashboard Screenshot (first render)</div>
          <img src="data:image/png;base64,{{ r.screenshot_b64 }}" alt="Dashboard screenshot" onclick="openLightbox(this)"/>
        </div>
        {% endif %}

      </div>
    </div>
    {% endfor %}
  </div>
</div>

<div class="footer">
  Generated by <strong>Tableau Dashboard Testing Framework</strong> — Performance Testing &nbsp;|&nbsp; {{ run_date }}
</div>

<div class="lightbox" id="lightbox" onclick="closeLightbox()">
  <img id="lightbox-img" src="" alt="Full size"/>
</div>

<script>
function toggle(header) {
  header.classList.toggle('open');
  header.nextElementSibling.classList.toggle('open');
}
function openLightbox(img) {
  event.stopPropagation();
  document.getElementById('lightbox-img').src = img.src;
  document.getElementById('lightbox').classList.add('show');
}
function closeLightbox() {
  document.getElementById('lightbox').classList.remove('show');
}
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeLightbox(); });
document.querySelectorAll('.result-card.fail .card-header').forEach(h => {
  h.classList.add('open');
  h.nextElementSibling.classList.add('open');
});
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# PerformanceReporter
# ---------------------------------------------------------------------------

class PerformanceReporter:
    def __init__(
        self,
        run_dir: Path,
        config: TestConfig,
        results: List[PerfDashboardResult],
    ):
        self.run_dir = run_dir
        self.config = config
        self.results = results

    def generate(self) -> Path:
        """Generate both the HTML report and CSV file. Returns the HTML path."""
        html_path = self._generate_html()
        csv_path = self._generate_csv()
        return html_path

    # ------------------------------------------------------------------

    def _generate_html(self) -> Path:
        rows = []
        for r in self.results:
            iter_data = [
                {
                    "iteration": it.iteration,
                    "first_render_ms": it.first_render_ms,
                    "interaction_ms": it.interaction_ms,
                }
                for it in r.iterations
            ]
            # Compute chart max for bar scaling
            all_times = [it.first_render_ms for it in r.iterations if it.first_render_ms > 0]
            all_times += [it.interaction_ms for it in r.iterations if it.interaction_ms > 0]
            chart_max = max(all_times) if all_times else 1

            rows.append({
                "label": r.label,
                "url": r.url,
                "passed": r.passed,
                "first_render_min": r.first_render_min,
                "first_render_max": r.first_render_max,
                "first_render_avg": r.first_render_avg,
                "interaction_min": r.interaction_min,
                "interaction_max": r.interaction_max,
                "interaction_avg": r.interaction_avg,
                "first_render_threshold": r.first_render_threshold,
                "interaction_threshold": r.interaction_threshold,
                "first_render_passed": r.first_render_passed,
                "interaction_passed": r.interaction_passed,
                "iterations": iter_data,
                "chart_max": chart_max,
                "screenshot_b64": _img_b64(r.screenshot_path),
            })

        passed = sum(1 for r in rows if r["passed"])
        data = {
            "run_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "run_dir": str(self.run_dir),
            "iterations": self.config.performance.iterations,
            "total": len(rows),
            "passed": passed,
            "failed": len(rows) - passed,
            "results": rows,
        }

        html = Template(_PERF_TEMPLATE).render(**data)
        out = self.run_dir / "report.html"
        out.write_text(html, encoding="utf-8")
        return out

    # ------------------------------------------------------------------

    def _generate_csv(self) -> Path:
        out = self.run_dir / "performance_results.csv"
        with open(out, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "dashboard_label",
                "dashboard_url",
                "iteration",
                "first_render_ms",
                "interaction_ms",
                "first_render_threshold_ms",
                "interaction_threshold_ms",
                "first_render_avg_ms",
                "interaction_avg_ms",
                "first_render_pass",
                "interaction_pass",
                "overall_pass",
            ])
            for r in self.results:
                for it in r.iterations:
                    writer.writerow([
                        r.label,
                        r.url,
                        it.iteration,
                        f"{it.first_render_ms:.0f}" if it.first_render_ms >= 0 else "ERROR",
                        f"{it.interaction_ms:.0f}" if it.interaction_ms >= 0 else "ERROR",
                        f"{r.first_render_threshold:.0f}",
                        f"{r.interaction_threshold:.0f}",
                        f"{r.first_render_avg:.0f}",
                        f"{r.interaction_avg:.0f}",
                        r.first_render_passed,
                        r.interaction_passed,
                        r.passed,
                    ])
        return out


# ---------------------------------------------------------------------------

def _img_b64(path: str) -> str:
    if not path:
        return None
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None
