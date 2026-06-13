#!/usr/bin/env python3
"""
Base Report Generator
Abstract base class for all test report generators with shared functionality
"""

from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import json


class BaseReportGenerator(ABC):
    """
    Abstract base class for generating enhanced HTML test reports
    
    Provides:
    - Common CSS styling and responsive design
    - Chart.js integration for visual analytics
    - Reusable HTML components (cards, tables, charts, navigation)
    - Interactive JavaScript (expand/collapse, filters, tabs)
    - Self-contained HTML output (no external dependencies except Chart.js CDN)
    """
    
    def __init__(self, input_path: str, output_path: str, title: str):
        """
        Initialize report generator
        
        Args:
            input_path: Path to input test results (JSON)
            output_path: Path to output HTML report
            title: Report title
        """
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self.title = title
        self.report_data = {}
        
    @abstractmethod
    def load_data(self) -> bool:
        """Load and validate input data - must be implemented by subclasses"""
        pass
    
    @abstractmethod
    def parse_data(self) -> bool:
        """Parse input data into report structure - must be implemented by subclasses"""
        pass
    
    @abstractmethod
    def _generate_content_sections(self) -> str:
        """Generate test-specific content sections - must be implemented by subclasses"""
        pass
    
    def generate_html(self) -> bool:
        """Generate complete HTML report"""
        html = self._build_complete_html()
        
        try:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.output_path, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"✅ Generated HTML report: {self.output_path}")
            return True
        except Exception as e:
            print(f"❌ Error writing HTML report: {e}")
            return False
    
    def generate_report(self) -> bool:
        """Main method to generate the complete report"""
        print(f"🔄 Generating {self.title}...")
        
        if not self.load_data():
            return False
        
        if not self.parse_data():
            return False
        
        if not self.generate_html():
            return False
        
        print("✅ Report generation complete!")
        return True
    
    def _build_complete_html(self) -> str:
        """Build complete self-contained HTML document"""
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.report_data.get('metadata', {}).get('title', self.title)}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0"></script>
    {self._generate_css()}
</head>
<body>
    {self._generate_header()}
    {self._generate_navigation()}
    {self._generate_content_sections()}
    {self._generate_footer()}
    {self._generate_javascript()}
</body>
</html>'''
    
    def _generate_css(self) -> str:
        """Generate embedded CSS - shared styles for all report types"""
        return '''<style>
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

:root {
    --success: #10b981;
    --fail: #ef4444;
    --error: #f59e0b;
    --skip: #9ca3af;
    --undefined: #9ca3af;
    --primary: #667eea;
    --primary-dark: #5a67d8;
    --bg-light: #f9fafb;
    --bg-white: #ffffff;
    --text-dark: #1f2937;
    --text-gray: #6b7280;
    --border: #e5e7eb;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    background: var(--bg-light);
    color: var(--text-dark);
    line-height: 1.6;
}

.report-header {
    background: linear-gradient(135deg, var(--primary) 0%, #764ba2 100%);
    color: white;
    padding: 32px 0;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}

.container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 0 24px;
}

.header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 24px;
}

.title-section h1 {
    font-size: 32px;
    margin-bottom: 8px;
}

.subtitle {
    font-size: 16px;
    opacity: 0.9;
}

.meta-info {
    display: flex;
    gap: 24px;
    flex-wrap: wrap;
}

.meta-item {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.meta-item .label {
    font-size: 12px;
    opacity: 0.8;
    text-transform: uppercase;
}

.meta-item .value {
    font-size: 18px;
    font-weight: 600;
}

.report-nav {
    background: rgba(255, 255, 255, 0.1);
    padding: 0;
    margin-top: 16px;
    border-radius: 8px;
    display: flex;
    overflow: hidden;
}

.nav-link {
    color: white;
    text-decoration: none;
    padding: 12px 24px;
    transition: background 0.3s;
    flex: 1;
    text-align: center;
}

.nav-link:hover {
    background: rgba(255, 255, 255, 0.2);
}

.nav-link.active {
    background: rgba(255, 255, 255, 0.3);
}

section {
    padding: 32px 0;
}

h2 {
    font-size: 24px;
    margin-bottom: 24px;
    color: var(--text-dark);
}

h3 {
    font-size: 18px;
    margin-bottom: 16px;
    color: var(--text-dark);
}

.summary-cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 20px;
    margin-bottom: 32px;
}

.summary-card {
    background: white;
    padding: 24px;
    border-radius: 12px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    display: flex;
    align-items: center;
    gap: 16px;
}

.card-icon {
    font-size: 40px;
}

.card-content {
    flex: 1;
}

.card-value {
    font-size: 36px;
    font-weight: 700;
    line-height: 1;
    margin-bottom: 4px;
}

.card-label {
    font-size: 13px;
    color: var(--text-gray);
    text-transform: uppercase;
}

.summary-card.total { border-left: 4px solid var(--primary); }
.summary-card.passed { border-left: 4px solid var(--success); }
.summary-card.passed .card-value { color: var(--success); }
.summary-card.failed { border-left: 4px solid var(--fail); }
.summary-card.failed .card-value { color: var(--fail); }
.summary-card.error { border-left: 4px solid var(--error); }
.summary-card.error .card-value { color: var(--error); }
.summary-card.skipped { border-left: 4px solid var(--skip); }
.summary-card.skipped .card-value { color: var(--skip); }

.charts-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
    gap: 24px;
    margin-bottom: 32px;
}

.chart-card {
    background: white;
    padding: 24px;
    border-radius: 12px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.chart-card h3 {
    font-size: 18px;
    margin-bottom: 16px;
    color: var(--text-dark);
}

.stats-table {
    background: white;
    padding: 24px;
    border-radius: 12px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    margin-bottom: 32px;
}

.stats-table table {
    width: 100%;
    border-collapse: collapse;
}

.stats-table th, .stats-table td {
    padding: 12px;
    text-align: left;
    border-bottom: 1px solid var(--border);
}

.stats-table th {
    background: var(--bg-light);
    font-weight: 600;
}

.item-card {
    background: white;
    margin-bottom: 20px;
    border-radius: 12px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    overflow: hidden;
    border: 2px solid transparent;
    transition: all 0.3s;
}

.item-card:hover {
    box-shadow: 0 4px 8px rgba(0,0,0,0.15);
}

.item-card.passed { border-left: 4px solid var(--success); }
.item-card.failed { border-left: 4px solid var(--fail); }
.item-card.error { border-left: 4px solid var(--error); }
.item-card.skipped { border-left: 4px solid var(--skip); }

.item-header {
    padding: 20px;
    background: var(--bg-light);
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    user-select: none;
}

.item-header:hover {
    background: #f3f4f6;
}

.item-title {
    display: flex;
    align-items: center;
    gap: 12px;
    flex: 1;
}

.expand-icon {
    font-size: 14px;
    color: var(--text-gray);
    transition: transform 0.3s;
}

.item-card.expanded .expand-icon {
    transform: rotate(90deg);
}

.item-title h3, .item-title h4 {
    font-weight: 600;
}

.tag {
    background: var(--primary);
    color: white;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 500;
}

.tags {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-top: 8px;
}

.item-stats {
    display: flex;
    gap: 16px;
    align-items: center;
}

.count {
    font-size: 14px;
    color: var(--text-gray);
}

.pass-rate {
    font-weight: 600;
    font-size: 16px;
    color: var(--primary);
}

.status-indicator {
    font-size: 24px;
    line-height: 1;
}

.status-indicator.passed { color: var(--success); }
.status-indicator.failed { color: var(--fail); }
.status-indicator.error { color: var(--error); }
.status-indicator.skipped { color: var(--skip); }

.item-body {
    padding: 20px;
    display: none;
}

.item-body.show {
    display: block;
}

.description {
    color: var(--text-gray);
    font-style: italic;
    margin-bottom: 20px;
    padding: 12px;
    background: var(--bg-light);
    border-radius: 4px;
}

.duration {
    font-size: 13px;
    color: var(--text-gray);
}

.status-badge {
    padding: 4px 12px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
}

.status-badge.passed {
    background: #d1fae5;
    color: #065f46;
}

.status-badge.failed {
    background: #fee2e2;
    color: #991b1b;
}

.status-badge.error {
    background: #fef3c7;
    color: #92400e;
}

.status-badge.skipped {
    background: #f3f4f6;
    color: #6b7280;
}

.error-details {
    margin-top: 12px;
    background: white;
    border-radius: 4px;
    padding: 12px;
    border-left: 4px solid var(--fail);
}

.error-header {
    font-weight: 600;
    color: var(--fail);
    margin-bottom: 8px;
}

.error-message {
    font-family: 'Courier New', monospace;
    font-size: 13px;
    color: var(--text-dark);
    white-space: pre-wrap;
    background: #fef2f2;
    padding: 8px;
    border-radius: 4px;
}

.controls {
    background: white;
    padding: 20px;
    border-radius: 12px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    margin-bottom: 24px;
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
}

.controls input, .controls select, .controls button {
    padding: 10px 16px;
    border: 1px solid var(--border);
    border-radius: 6px;
    font-size: 14px;
}

.controls input {
    flex: 1;
    min-width: 200px;
}

.controls button {
    background: var(--primary);
    color: white;
    border: none;
    cursor: pointer;
    font-weight: 500;
    transition: background 0.3s;
}

.controls button:hover {
    background: var(--primary-dark);
}

.report-footer {
    background: var(--text-dark);
    color: white;
    padding: 24px 0;
    text-align: center;
    margin-top: 40px;
}

.report-footer p {
    opacity: 0.8;
    margin: 4px 0;
}

@media (max-width: 768px) {
    .header-content {
        flex-direction: column;
        align-items: flex-start;
    }
    
    .summary-cards {
        grid-template-columns: 1fr;
    }
    
    .charts-grid {
        grid-template-columns: 1fr;
    }
    
    .controls {
        flex-direction: column;
    }
    
    .controls input, .controls select, .controls button {
        width: 100%;
    }
}

@media print {
    .controls, .report-nav {
        display: none;
    }
    
    .item-body {
        display: block !important;
    }
}
</style>'''
    
    def _generate_header(self) -> str:
        """Generate report header with title, metadata, and status"""
        meta = self.report_data.get('metadata', {})
        summary = self.report_data.get('summary', {})
        
        # Determine overall status
        failed_count = summary.get('failed', summary.get('failed_scenarios', summary.get('failed_tests', 0)))
        error_count = summary.get('error', summary.get('error_scenarios', 0))
        overall_status = "passed" if (failed_count == 0 and error_count == 0) else "failed"
        status_icon = "✅" if overall_status == "passed" else "❌"
        
        # Format duration
        duration = summary.get('total_duration', 0)
        duration_str = self._format_duration(duration)
        
        return f'''
<header class="report-header">
    <div class="container">
        <div class="header-content">
            <div class="title-section">
                <h1>{meta.get('icon', '📊')} {meta.get('title', self.title)}</h1>
                <p class="subtitle">{meta.get('subtitle', 'Test Results')}</p>
            </div>
            <div class="meta-info">
                <div class="meta-item">
                    <span class="label">Generated</span>
                    <span class="value">{meta.get('generated_at', datetime.now().strftime('%B %d, %Y %H:%M:%S'))}</span>
                </div>
                <div class="meta-item">
                    <span class="label">Duration</span>
                    <span class="value">{duration_str}</span>
                </div>
                <div class="meta-item">
                    <span class="label">Status</span>
                    <span class="value">{status_icon} {overall_status.upper()}</span>
                </div>
            </div>
        </div>
    </div>
</header>'''
    
    def _generate_navigation(self) -> str:
        """Generate navigation tabs - can be overridden by subclasses"""
        tabs = self.report_data.get('navigation_tabs', [
            ('overview', '📊 Overview'),
            ('details', '📋 Details'),
            ('analytics', '📈 Analytics')
        ])
        
        tabs_html = ''
        for idx, (tab_id, tab_label) in enumerate(tabs):
            active_class = 'active' if idx == 0 else ''
            tabs_html += f'<a href="#{tab_id}" class="nav-link {active_class}" onclick="event.preventDefault(); showTab(\'{tab_id}\'); return false;">{tab_label}</a>\n'
        
        return f'''
<div class="report-header">
    <div class="container">
        <nav class="report-nav">
            {tabs_html}
        </nav>
    </div>
</div>'''
    
    def _generate_footer(self) -> str:
        """Generate report footer"""
        return '''
<footer class="report-footer">
    <div class="container">
        <p>NexusAI Test Reports</p>
    </div>
</footer>'''
    
    def _generate_javascript(self) -> str:
        """Generate embedded JavaScript for interactivity"""
        return '''<script>
// Tab switching
function showTab(tabName) {
    document.querySelectorAll('section[id]').forEach(el => {
        el.style.display = 'none';
    });
    const section = document.getElementById(tabName);
    if (section) {
        section.style.display = 'block';
    }
    
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
    });
    event.target.classList.add('active');
}

// Toggle expandable items
function toggleItem(itemId) {
    const body = document.getElementById(itemId + '-body');
    const card = document.getElementById(itemId);
    
    if (body && card) {
        if (body.classList.contains('show')) {
            body.classList.remove('show');
            body.style.display = 'none';
            card.classList.remove('expanded');
        } else {
            body.classList.add('show');
            body.style.display = 'block';
            card.classList.add('expanded');
        }
    }
}

// Expand/collapse all
function expandAll() {
    document.querySelectorAll('.item-body').forEach(el => {
        el.classList.add('show');
        el.style.display = 'block';
    });
    document.querySelectorAll('.item-card').forEach(el => el.classList.add('expanded'));
}

function collapseAll() {
    document.querySelectorAll('.item-body').forEach(el => {
        el.classList.remove('show');
        el.style.display = 'none';
    });
    document.querySelectorAll('.item-card').forEach(el => el.classList.remove('expanded'));
}

function expandAllFailed() {
    document.querySelectorAll('.item-card.failed .item-body, .item-card.error .item-body').forEach(el => {
        el.classList.add('show');
        el.style.display = 'block';
    });
    document.querySelectorAll('.item-card.failed, .item-card.error').forEach(el => {
        el.classList.add('expanded');
    });
}

// Filter items
function filterItems(searchBoxId, itemSelector) {
    const searchTerm = document.getElementById(searchBoxId).value.toLowerCase();
    document.querySelectorAll(itemSelector).forEach(card => {
        const text = card.textContent.toLowerCase();
        card.style.display = text.includes(searchTerm) ? 'block' : 'none';
    });
}

function filterByStatus(filterId, itemSelector) {
    const status = document.getElementById(filterId).value;
    document.querySelectorAll(itemSelector).forEach(card => {
        if (status === 'all' || card.classList.contains(status)) {
            card.style.display = 'block';
        } else {
            card.style.display = 'none';
        }
    });
}
</script>'''
    
    def _generate_summary_cards(self, cards_data: List[Dict[str, Any]]) -> str:
        """Generate summary cards grid"""
        cards_html = ''
        for card in cards_data:
            cards_html += f'''
            <div class="summary-card {card.get('type', '')}">
                <div class="card-icon">{card.get('icon', '📊')}</div>
                <div class="card-content">
                    <div class="card-value">{card.get('value', 0)}</div>
                    <div class="card-label">{card.get('label', '')}</div>
                </div>
            </div>
'''
        
        return f'''
        <div class="summary-cards">
{cards_html}
        </div>'''
    
    def _generate_pie_chart(self, chart_id: str, title: str, data: Dict[str, int]) -> str:
        """Generate pie chart HTML and initialize script"""
        labels = list(data.keys())
        values = list(data.values())
        colors = {
            'Passed': 'rgb(16, 185, 129)',
            'Failed': 'rgb(239, 68, 68)',
            'Error': 'rgb(245, 158, 11)',
            'Skipped': 'rgb(156, 163, 175)'
        }
        bg_colors = [colors.get(label, 'rgb(102, 126, 234)') for label in labels]
        
        return f'''
        <div class="chart-card">
            <h3>{title}</h3>
            <canvas id="{chart_id}"></canvas>
        </div>
        <script>
        document.addEventListener('DOMContentLoaded', function() {{
            const ctx = document.getElementById('{chart_id}');
            if (ctx) {{
                new Chart(ctx, {{
                    type: 'pie',
                    data: {{
                        labels: {json.dumps(labels)},
                        datasets: [{{
                            data: {json.dumps(values)},
                            backgroundColor: {json.dumps(bg_colors)}
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: true,
                        plugins: {{
                            legend: {{
                                position: 'bottom'
                            }}
                        }}
                    }}
                }});
            }}
        }});
        </script>'''
    
    def _generate_bar_chart(self, chart_id: str, title: str, labels: List[str], datasets: List[Dict[str, Any]]) -> str:
        """Generate bar chart HTML and initialize script"""
        return f'''
        <div class="chart-card">
            <h3>{title}</h3>
            <canvas id="{chart_id}"></canvas>
        </div>
        <script>
        document.addEventListener('DOMContentLoaded', function() {{
            const ctx = document.getElementById('{chart_id}');
            if (ctx) {{
                new Chart(ctx, {{
                    type: 'bar',
                    data: {{
                        labels: {json.dumps(labels)},
                        datasets: {json.dumps(datasets)}
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: true,
                        scales: {{
                            x: {{
                                stacked: true
                            }},
                            y: {{
                                stacked: true,
                                beginAtZero: true
                            }}
                        }},
                        plugins: {{
                            legend: {{
                                position: 'bottom'
                            }}
                        }}
                    }}
                }});
            }}
        }});
        </script>'''
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format"""
        if seconds < 1:
            return f"{seconds * 1000:.0f}ms"
        elif seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
    
    def _get_status_icon(self, status: str) -> str:
        """Get icon for test status"""
        icons = {
            'passed': '✓',
            'failed': '✗',
            'error': '⚠',
            'skipped': '○',
            'undefined': '?'
        }
        return icons.get(status.lower(), '?')
    
    def _sanitize_html(self, text: str) -> str:
        """Sanitize text for HTML output"""
        if not text:
            return ''
        return (text.replace('&', '&amp;')
                   .replace('<', '&lt;')
                   .replace('>', '&gt;')
                   .replace('"', '&quot;')
                   .replace("'", '&#39;'))

