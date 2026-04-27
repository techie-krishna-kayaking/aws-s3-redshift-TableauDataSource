"""
reporter.py — Generates a self-contained HTML report for every test run.

The report:
  • Works completely offline (all images embedded as base64)
  • Dark-themed, premium layout with pass/fail colour coding
  • Shows SSIM scores, violation tables, and side-by-side diff images
  • One file to share — open in any browser
"""
from __future__ import annotations

import base64
import json
from datetime import datetime
from pathlib import Path
from typing import List, Union

from jinja2 import Template

from bi_regression.config_parser import TestConfig


# ---------------------------------------------------------------------------
# HTML template (single self-contained file — no external deps)
# ---------------------------------------------------------------------------

_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Tableau Test Report — {{ run_date }}</title>
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

    /* ---- Header ---- */
    .header {
      background: linear-gradient(135deg, #1e2240 0%, #0f1117 100%);
      border-bottom: 1px solid var(--border);
      padding: 32px 40px;
    }
    .header h1 { font-size: 28px; font-weight: 700; letter-spacing: -0.5px; }
    .header h1 span { color: var(--accent); }
    .meta { color: var(--muted); font-size: 13px; margin-top: 6px; }
    .meta a { color: var(--accent); text-decoration: none; word-break: break-all; }
    .meta a:hover { text-decoration: underline; }

    /* ---- Dashboard links ---- */
    .dash-links {
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 16px 40px;
      display: flex; flex-wrap: wrap; gap: 24px;
      font-size: 13px;
    }
    .dash-link-item { display: flex; align-items: center; gap: 8px; }
    .dash-link-label {
      font-size: 11px; font-weight: 700; text-transform: uppercase;
      letter-spacing: 1px; color: var(--muted);
      padding: 2px 8px; border-radius: 4px;
      background: rgba(255,255,255,0.05);
    }
    .dash-link-url { color: var(--accent); text-decoration: none; max-width: 600px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .dash-link-url:hover { text-decoration: underline; }

    /* ---- Summary cards ---- */
    .summary { display: flex; gap: 16px; padding: 24px 40px; flex-wrap: wrap; }
    .stat-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 20px 28px;
      min-width: 150px;
      flex: 1;
    }
    .stat-card .label { font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: var(--muted); }
    .stat-card .value { font-size: 36px; font-weight: 700; margin-top: 6px; }
    .stat-card.pass .value { color: var(--pass); }
    .stat-card.fail .value { color: var(--fail); }
    .stat-card.total .value { color: var(--accent); }
    .stat-card.type  .value { font-size: 22px; }

    /* ---- Section ---- */
    .section { padding: 0 40px 40px; }
    .section h2 { font-size: 18px; font-weight: 600; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 1px solid var(--border); }

    /* ---- Result cards ---- */
    .results { display: flex; flex-direction: column; gap: 20px; }
    .result-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      overflow: hidden;
    }
    .result-card.pass { border-left: 4px solid var(--pass); }
    .result-card.fail { border-left: 4px solid var(--fail); }

    .card-header {
      display: flex; align-items: center; gap: 16px;
      padding: 16px 20px;
      cursor: pointer;
      user-select: none;
    }
    .card-header:hover { background: rgba(255,255,255,0.03); }
    .badge {
      font-size: 11px; font-weight: 700; padding: 3px 10px;
      border-radius: 20px; text-transform: uppercase; letter-spacing: 1px;
    }
    .badge.pass { background: rgba(34,197,94,0.15); color: var(--pass); border: 1px solid var(--pass); }
    .badge.fail { background: rgba(239,68,68,0.15);  color: var(--fail); border: 1px solid var(--fail); }
    .tab-name { font-size: 15px; font-weight: 600; flex: 1; }
    .ssim-score { font-size: 13px; color: var(--muted); }
    .scenario-badge {
      font-size: 11px; font-weight: 600; padding: 2px 8px;
      border-radius: 10px; background: rgba(91,106,240,0.15);
      color: var(--accent); border: 1px solid var(--accent);
    }
    .arrow { color: var(--muted); font-size: 18px; transition: transform 0.2s; }
    .card-header.open .arrow { transform: rotate(90deg); }

    .card-body { display: none; padding: 0 20px 20px; }
    .card-body.open { display: block; }

    /* ---- Image gallery (baseline / target / diff) ---- */
    .img-gallery { display: flex; flex-direction: column; gap: 20px; margin-top: 16px; }
    .img-pair { display: flex; gap: 16px; }
    .img-pair .img-box { flex: 1; min-width: 0; }
    .img-box-label {
      font-size: 11px; text-transform: uppercase; letter-spacing: 1px;
      color: var(--muted); margin-bottom: 8px; display: flex; align-items: center; gap: 8px;
    }
    .img-box-label .dot {
      width: 8px; height: 8px; border-radius: 50%; display: inline-block;
    }
    .dot.baseline { background: var(--accent); }
    .dot.target   { background: var(--warn); }
    .dot.diff     { background: var(--fail); }
    .img-box img { width: 100%; border-radius: 8px; border: 1px solid var(--border); cursor: pointer; }
    .img-box img:hover { border-color: var(--accent); }

    .diff-full { margin-top: 16px; }
    .diff-full-label {
      font-size: 12px; text-transform: uppercase; letter-spacing: 1px;
      color: var(--muted); margin-bottom: 8px; font-weight: 600;
    }
    .diff-full img { width: 100%; border-radius: 8px; border: 1px solid var(--border); }

    /* ---- Filter list ---- */
    .filter-list { margin-top: 12px; display: flex; flex-wrap: wrap; gap: 8px; }
    .filter-chip {
      font-size: 12px; padding: 3px 10px; border-radius: 6px;
      background: rgba(255,255,255,0.05); border: 1px solid var(--border);
    }
    .filter-chip .fn { color: var(--muted); }
    .filter-chip .fv { color: var(--text); font-weight: 600; }

    /* ---- Diff image (legacy) ---- */
    .diff-container { margin-top: 16px; }
    .diff-label { font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: var(--muted); margin-bottom: 8px; }
    .diff-img { width: 100%; border-radius: 8px; border: 1px solid var(--border); }

    /* ---- Violations table ---- */
    .violations-table { width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 13px; }
    .violations-table th {
      text-align: left; padding: 8px 12px;
      background: rgba(255,255,255,0.05);
      color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 1px;
    }
    .violations-table td { padding: 8px 12px; border-top: 1px solid var(--border); vertical-align: top; }
    .violations-table tr:hover td { background: rgba(255,255,255,0.02); }
    .vtype { font-weight: 600; }
    .vtype.font_family { color: #a78bfa; }
    .vtype.font_size   { color: #60a5fa; }
    .vtype.color       { color: #f97316; }
    .found-val { font-family: monospace; color: var(--fail); }
    .el-text { color: var(--muted); font-style: italic; max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

    /* ---- Lightbox ---- */
    .lightbox { display:none; position:fixed; z-index:1000; top:0; left:0; width:100vw; height:100vh;
      background:rgba(0,0,0,0.92); justify-content:center; align-items:center; cursor:zoom-out; }
    .lightbox.show { display:flex; }
    .lightbox img { max-width:95vw; max-height:95vh; border-radius:8px; }

    /* ---- Footer ---- */
    .footer { text-align: center; color: var(--muted); font-size: 12px; padding: 24px; border-top: 1px solid var(--border); margin-top: 20px; }
  </style>
</head>
<body>

<div class="header">
  <h1>Tableau <span>Dashboard Test</span> Report</h1>
  <p class="meta">
    Run Date: {{ run_date }}
    &nbsp;|&nbsp; Mode: <strong>{{ test_type_display }}</strong>
    &nbsp;|&nbsp; Output: {{ run_dir }}
  </p>
</div>

{% if dashboard_links %}
<div class="dash-links">
  {% for dl in dashboard_links %}
  <div class="dash-link-item">
    <span class="dash-link-label">{{ dl.label }}</span>
    <a class="dash-link-url" href="{{ dl.url }}" target="_blank" title="{{ dl.url }}">{{ dl.url }}</a>
  </div>
  {% endfor %}
</div>
{% endif %}

<div class="summary">
  <div class="stat-card type">
    <div class="label">Test Type</div>
    <div class="value">{{ test_type_display }}</div>
  </div>
  <div class="stat-card total">
    <div class="label">Total Tests</div>
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
  {% if avg_ssim is not none %}
  <div class="stat-card total">
    <div class="label">Avg SSIM</div>
    <div class="value" style="font-size:26px;">{{ avg_ssim }}</div>
  </div>
  {% endif %}
  {% if scenario_count %}
  <div class="stat-card total">
    <div class="label">Filter Scenarios</div>
    <div class="value" style="font-size:26px;">{{ scenario_count }}</div>
  </div>
  {% endif %}
</div>

<div class="section">
  <h2>Results</h2>
  <div class="results">
    {% for r in results %}
    <div class="result-card {{ 'pass' if r.passed else 'fail' }}">
      <div class="card-header" onclick="toggle(this)">
        <span class="badge {{ 'pass' if r.passed else 'fail' }}">{{ 'PASS' if r.passed else 'FAIL' }}</span>
        <span class="tab-name">{{ r.tab_name }}{% if r.scenario_label %} — {{ r.scenario_label }}{% endif %}</span>
        {% if r.scenario_label %}
        <span class="scenario-badge">{{ r.scenario_label }}</span>
        {% endif %}
        {% if r.ssim_score is not none %}
        <span class="ssim-score">SSIM: {{ "%.4f"|format(r.ssim_score) }}{% if r.diff_pixel_count %} · {{ r.diff_pixel_count }} diff px{% endif %}</span>
        {% endif %}
        {% if r.violation_count is not none %}
        <span class="ssim-score">{{ r.violation_count }} violation(s)</span>
        {% endif %}
        <span class="arrow">▶</span>
      </div>
      <div class="card-body">

        {% if r.filters %}
        <div class="filter-list">
          {% for f in r.filters %}
          <span class="filter-chip"><span class="fn">{{ f.name }}:</span> <span class="fv">{{ f.value }}</span></span>
          {% endfor %}
        </div>
        {% endif %}

        {% if r.baseline_b64 or r.target_b64 %}
        <div class="img-gallery">
          <div class="img-pair">
            {% if r.baseline_b64 %}
            <div class="img-box">
              <div class="img-box-label"><span class="dot baseline"></span> {{ r.label_a }} (Baseline)</div>
              <img src="data:image/png;base64,{{ r.baseline_b64 }}" alt="{{ r.label_a }} screenshot" onclick="openLightbox(this)"/>
            </div>
            {% endif %}
            {% if r.target_b64 %}
            <div class="img-box">
              <div class="img-box-label"><span class="dot target"></span> {{ r.label_b }} (Target)</div>
              <img src="data:image/png;base64,{{ r.target_b64 }}" alt="{{ r.label_b }} screenshot" onclick="openLightbox(this)"/>
            </div>
            {% endif %}
          </div>

          {% if r.diff_image_b64 %}
          <div class="diff-full">
            <div class="diff-full-label"><span class="dot diff" style="display:inline-block;margin-right:6px;"></span> Side-by-side diff ({{ r.label_a }} vs {{ r.label_b }}) — differences highlighted in red</div>
            <img class="diff-img" src="data:image/png;base64,{{ r.diff_image_b64 }}" alt="Diff image" onclick="openLightbox(this)"/>
          </div>
          {% endif %}
        </div>

        {% elif r.diff_image_b64 %}
        <div class="diff-container">
          <div class="diff-label">Side-by-side comparison ({{ r.label_a }} vs {{ r.label_b }})</div>
          <img class="diff-img" src="data:image/png;base64,{{ r.diff_image_b64 }}" alt="Diff image" onclick="openLightbox(this)"/>
        </div>
        {% endif %}

        {% if r.annotated_b64 %}
        <div class="diff-container">
          <div class="diff-label">Annotated screenshot — violations highlighted</div>
          <img class="diff-img" src="data:image/png;base64,{{ r.annotated_b64 }}" alt="Annotated screenshot" onclick="openLightbox(this)"/>
        </div>
        {% endif %}

        {% if r.violations %}
        <table class="violations-table">
          <thead><tr>
            <th>Type</th><th>Found</th><th>Expected</th><th>Element Text</th>
          </tr></thead>
          <tbody>
          {% for v in r.violations %}
          <tr>
            <td><span class="vtype {{ v.violation_type }}">{{ v.violation_type | replace("_"," ") }}</span></td>
            <td><span class="found-val">{{ v.found }}</span></td>
            <td>{{ v.expected | join(", ") }}</td>
            <td><span class="el-text" title="{{ v.element_text }}">{{ v.element_text }}</span></td>
          </tr>
          {% endfor %}
          </tbody>
        </table>
        {% endif %}

        {% if r.reason %}
        <p style="color:var(--warn); margin-top:12px;">⚠ {{ r.reason }}</p>
        {% endif %}

      </div>
    </div>
    {% endfor %}
  </div>
</div>

<div class="footer">
  Generated by <strong>Tableau Dashboard Testing Framework</strong> &nbsp;|&nbsp; {{ run_date }}
</div>

<!-- Lightbox for full-size image view -->
<div class="lightbox" id="lightbox" onclick="closeLightbox()">
  <img id="lightbox-img" src="" alt="Full size"/>
</div>

<script>
function toggle(header) {
  header.classList.toggle('open');
  const body = header.nextElementSibling;
  body.classList.toggle('open');
}
function openLightbox(img) {
  event.stopPropagation();
  const lb = document.getElementById('lightbox');
  document.getElementById('lightbox-img').src = img.src;
  lb.classList.add('show');
}
function closeLightbox() {
  document.getElementById('lightbox').classList.remove('show');
}
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeLightbox(); });
// Auto-expand failed cards
document.querySelectorAll('.result-card.fail .card-header').forEach(h => {
  h.classList.add('open');
  h.nextElementSibling.classList.add('open');
});
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------

class Reporter:
    def __init__(self, run_dir: Path, config: TestConfig, results: list):
        self.run_dir = run_dir
        self.config = config
        self.results = results

    def generate(self) -> Path:
        """Render the HTML report and return its path."""
        report_data = self._build_report_data()
        html = Template(_TEMPLATE).render(**report_data)
        out = self.run_dir / "report.html"
        out.write_text(html, encoding="utf-8")
        return out

    # ------------------------------------------------------------------

    def _build_report_data(self) -> dict:
        test_type = self.config.test_type
        rows = []
        total_ssim = []

        # ---- Collect dashboard links and scenario info -----------------
        dashboard_links = []
        scenario_count = 0
        if test_type == "comparison" and self.config.comparison:
            cfg_list = self.config.comparison if isinstance(self.config.comparison, list) else [self.config.comparison]
            for cfg in cfg_list:
                dashboard_links.append({"label": cfg.label_1, "url": cfg.dashboard_url_1})
                dashboard_links.append({"label": cfg.label_2, "url": cfg.dashboard_url_2})
                if cfg.filter_scenarios:
                    scenario_count += len(cfg.filter_scenarios)

        # ---- Build scenario filter lookup for display ------------------
        scenario_filters = {}
        if test_type == "comparison" and self.config.comparison:
            cfg_list = self.config.comparison if isinstance(self.config.comparison, list) else [self.config.comparison]
            for cfg in cfg_list:
                if cfg.filter_scenarios:
                    for s in cfg.filter_scenarios:
                        scenario_filters[s.label] = [
                            {"name": f.name, "value": f.value}
                            for f in s.filters
                        ]

        for r in self.results:
            row = {}

            if test_type == "comparison":
                # r is a DiffResult
                row["tab_name"]        = r.tab_name
                row["passed"]          = r.passed
                row["ssim_score"]      = r.ssim_score
                row["diff_pixel_count"] = r.diff_pixel_count
                row["violation_count"] = None
                row["violations"]      = []
                row["label_a"]         = r.label_a
                row["label_b"]         = r.label_b
                row["reason"]          = getattr(r, "reason", "")
                row["baseline_b64"]    = _img_b64(r.baseline_path)
                row["target_b64"]      = _img_b64(r.target_path)
                row["diff_image_b64"]  = _img_b64(r.diff_path)
                row["annotated_b64"]   = None
                row["scenario_label"]  = getattr(r, "scenario_label", "")
                row["filters"]         = scenario_filters.get(row["scenario_label"], [])
                if r.ssim_score and r.ssim_score > 0:
                    total_ssim.append(r.ssim_score)

            else:  # smoke
                # r is a TabSmokeResult
                row["tab_name"]        = r.tab_name
                row["passed"]          = r.passed
                row["ssim_score"]      = None
                row["diff_pixel_count"] = 0
                row["violation_count"] = len(r.violations)
                row["violations"]      = [
                    {
                        "violation_type": v.violation_type,
                        "found": v.found,
                        "expected": v.expected,
                        "element_text": v.element_text,
                    }
                    for v in r.violations
                ]
                row["label_a"]         = ""
                row["label_b"]         = ""
                row["reason"]          = getattr(r, "error", "") or ""
                row["baseline_b64"]    = None
                row["target_b64"]      = None
                row["diff_image_b64"]  = None
                row["annotated_b64"]   = _img_b64(r.annotated_path) if r.annotated_path else None
                row["scenario_label"]  = ""
                row["filters"]         = []

            rows.append(row)

        passed = sum(1 for r in rows if r["passed"])
        avg_ssim = f"{sum(total_ssim)/len(total_ssim):.4f}" if total_ssim else None

        _TYPE_LABELS = {
            "smoke": "SMOKE TESTING",
            "comparison": "REGRESSION / COMPARISON TESTING",
            "performance": "PERFORMANCE TESTING",
        }

        return {
            "run_date":         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "run_dir":          str(self.run_dir),
            "test_type":        test_type,
            "test_type_display": _TYPE_LABELS.get(test_type, test_type.upper()),
            "total":            len(rows),
            "passed":           passed,
            "failed":           len(rows) - passed,
            "avg_ssim":         avg_ssim,
            "dashboard_links":  dashboard_links,
            "scenario_count":   scenario_count,
            "results":          rows,
        }


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _img_b64(path: str) -> str | None:
    """Read an image file and return a base64 string, or None if not found."""
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    try:
        return base64.b64encode(p.read_bytes()).decode("utf-8")
    except Exception:
        return None
