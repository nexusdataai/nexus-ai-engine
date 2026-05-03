#!/usr/bin/env python3
"""
Endurance Test Report Generator
Generates professional HTML reports from endurance test JSON output
Refactored to use BaseReportGenerator framework
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import argparse

# Handle imports for both script and module usage
try:
    from .base_report_generator import BaseReportGenerator
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from base_report_generator import BaseReportGenerator


class EnduranceReportGenerator(BaseReportGenerator):
    """Generate enhanced HTML reports from endurance test JSON output"""
    
    def __init__(self, json_path: str, output_html_path: str, title: str = "Endurance Test Report"):
        super().__init__(json_path, output_html_path, title)
        self.endurance_data = {}
        
    def load_data(self):
        """Load endurance test JSON output"""
        try:
            with open(self.input_path, 'r') as f:
                self.endurance_data = json.load(f)
            print(f"✅ Loaded endurance test results from {self.input_path}")
            return True
        except Exception as e:
            print(f"❌ Error loading endurance JSON: {e}")
            return False
    
    def parse_data(self):
        """Parse endurance data into report structure"""
        test_info = self.endurance_data.get('test_info', {})
        summary = self.endurance_data.get('summary', {})
        performance = self.endurance_data.get('performance', {})
        health = self.endurance_data.get('health', {})
        failures = self.endurance_data.get('failures', {})
        config = self.endurance_data.get('config', {})
        
        # Calculate statistics
        total_tests = summary.get('total_tests', summary.get('total_iterations', 0))
        passed = summary.get('passed', 0)
        failed = summary.get('failed', 0)
        errors = summary.get('errors', 0)
        pass_rate = summary.get('pass_rate', 0)
        
        # Duration info
        duration_seconds = test_info.get('duration_seconds', 0)
        start_time = test_info.get('start_time', '')
        end_time = test_info.get('end_time', '')
        
        # Health info
        health_summary = health.get('summary', {})
        health_alerts = health.get('alerts', [])
        is_healthy = health.get('healthy', True)
        
        # Performance info
        avg_execution = performance.get('avg_execution_time', 0)
        max_execution = performance.get('max_execution_time', 0)
        min_execution = performance.get('min_execution_time', 0)
        tests_per_minute = summary.get('tests_per_minute', 0)
        
        # CPU and Memory stats
        cpu_stats = health_summary.get('cpu', {})
        memory_stats = health_summary.get('memory_gb', {})
        
        # Build report data
        self.report_data = {
            'metadata': {
                'title': self.title,
                'subtitle': 'Performance Endurance Test Results',
                'icon': '🏃',
                'generated_at': datetime.now().strftime('%B %d, %Y %H:%M:%S'),
                'timestamp': datetime.now().isoformat(),
                'start_time': start_time,
                'end_time': end_time,
            },
            'summary': {
                'total': total_tests,
                'passed': passed,
                'failed': failed,
                'errors': errors,
                'pass_rate': round(pass_rate, 1),
                'duration_seconds': duration_seconds,
                'duration_minutes': round(duration_seconds / 60, 1) if duration_seconds else 0,
                'tests_per_minute': round(tests_per_minute, 1),
                'interrupted': test_info.get('interrupted', False),
                'strategy': test_info.get('strategy', 'unknown'),
            },
            'performance': {
                'avg_execution_time': avg_execution,
                'max_execution_time': max_execution,
                'min_execution_time': min_execution,
            },
            'health': {
                'is_healthy': is_healthy,
                'cpu': cpu_stats,
                'memory': memory_stats,
                'alerts': health_alerts,
                'alert_count': len(health_alerts),
                'summary': health_summary,
            },
            'failures': failures,
            'config': config,
            'navigation_tabs': [
                ('overview', '📊 Overview'),
                ('performance', '⚡ Performance'),
                ('health', '💚 Health'),
                ('alerts', '🚨 Alerts'),
            ]
        }
        
        print(f"✅ Parsed endurance test: {total_tests} iterations, {pass_rate:.1f}% pass rate, {duration_seconds:.1f}s duration")
        return True
    
    def _generate_content_sections(self) -> str:
        """Generate endurance-specific content sections"""
        return (
            self._generate_overview_section() +
            self._generate_performance_section() +
            self._generate_health_section() +
            self._generate_alerts_section()
        )
    
    def _generate_overview_section(self) -> str:
        """Generate overview section with summary cards and charts"""
        s = self.report_data['summary']
        perf = self.report_data['performance']
        health = self.report_data['health']
        
        # Summary cards
        cards_data = [
            {'type': 'total', 'icon': '🔄', 'value': s['total'], 'label': 'Total Iterations'},
            {'type': 'passed', 'icon': '✅', 'value': s['passed'], 'label': 'Passed'},
            {'type': 'failed', 'icon': '❌', 'value': s['failed'], 'label': 'Failed'},
            {'type': 'error', 'icon': '⚠️', 'value': s['errors'], 'label': 'Errors'}
        ]
        
        # Pie chart data
        pie_data = {
            'Passed': s['passed'],
            'Failed': s['failed'],
            'Errors': s['errors']
        }
        
        # Status indicator
        status_class = 'passed' if s['pass_rate'] >= 95 else ('warning' if s['pass_rate'] >= 80 else 'failed')
        status_text = 'EXCELLENT' if s['pass_rate'] >= 95 else ('GOOD' if s['pass_rate'] >= 80 else 'NEEDS ATTENTION')
        
        # Health status
        health_class = 'passed' if health['is_healthy'] else 'failed'
        health_text = 'HEALTHY' if health['is_healthy'] else 'UNHEALTHY'
        
        return f'''
<section id="overview" class="overview-section">
    <div class="container">
        <h2>📊 Endurance Test Overview</h2>
        
        <div class="status-banner {status_class}">
            <div class="status-icon">{self._get_status_icon(status_class)}</div>
            <div class="status-info">
                <div class="status-title">{status_text}</div>
                <div class="status-subtitle">{s['pass_rate']}% Pass Rate over {s['duration_minutes']} minutes</div>
            </div>
            <div class="health-badge {health_class}">
                💚 {health_text}
            </div>
        </div>
        
        {self._generate_summary_cards(cards_data)}
        
        <div class="charts-grid">
            {self._generate_pie_chart('statusPieChart', 'Test Results Distribution', pie_data)}
            {self._generate_metrics_chart()}
        </div>
        
        <div class="stats-table">
            <h3>📈 Test Execution Details</h3>
            <table>
                <tr><th>Metric</th><th>Value</th></tr>
                <tr><td>Total Duration</td><td><strong>{s['duration_minutes']} minutes</strong> ({s['duration_seconds']:.1f}s)</td></tr>
                <tr><td>Tests Per Minute</td><td>{s['tests_per_minute']}</td></tr>
                <tr><td>Test Strategy</td><td>{s['strategy'].upper()}</td></tr>
                <tr><td>Pass Rate</td><td><strong style="color: {'var(--success)' if s['pass_rate'] >= 80 else 'var(--fail)'};">{s['pass_rate']}%</strong></td></tr>
                <tr><td>Test Interrupted</td><td>{'⚠️ Yes' if s['interrupted'] else '✅ No'}</td></tr>
                <tr><td>Avg Execution Time</td><td>{perf['avg_execution_time']*1000:.0f}ms</td></tr>
                <tr><td>Min Execution Time</td><td>{perf['min_execution_time']*1000:.0f}ms</td></tr>
                <tr><td>Max Execution Time</td><td>{perf['max_execution_time']*1000:.0f}ms</td></tr>
            </table>
        </div>
    </div>
</section>'''
    
    def _generate_metrics_chart(self) -> str:
        """Generate a chart showing key metrics"""
        perf = self.report_data['performance']
        
        return f'''
<div class="chart-container">
    <h3>⏱️ Execution Time Distribution</h3>
    <canvas id="executionTimeChart"></canvas>
    <script>
        new Chart(document.getElementById('executionTimeChart'), {{
            type: 'bar',
            data: {{
                labels: ['Min', 'Average', 'Max'],
                datasets: [{{
                    label: 'Execution Time (ms)',
                    data: [{perf['min_execution_time']*1000:.0f}, {perf['avg_execution_time']*1000:.0f}, {perf['max_execution_time']*1000:.0f}],
                    backgroundColor: ['rgb(16, 185, 129)', 'rgb(59, 130, 246)', 'rgb(245, 158, 11)']
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{
                    y: {{ beginAtZero: true, title: {{ display: true, text: 'Time (ms)' }} }}
                }}
            }}
        }});
    </script>
</div>'''
    
    def _generate_performance_section(self) -> str:
        """Generate performance analysis section"""
        s = self.report_data['summary']
        perf = self.report_data['performance']
        
        # Calculate throughput rating
        tpm = s['tests_per_minute']
        throughput_rating = 'Excellent' if tpm >= 100 else ('Good' if tpm >= 50 else ('Fair' if tpm >= 20 else 'Low'))
        throughput_color = 'var(--success)' if tpm >= 100 else ('var(--primary)' if tpm >= 50 else ('var(--warning)' if tpm >= 20 else 'var(--fail)'))
        
        return f'''
<section id="performance" class="performance-section" style="display:none;">
    <div class="container">
        <h2>⚡ Performance Analysis</h2>
        
        <div class="performance-grid">
            <div class="perf-card">
                <div class="perf-icon">🚀</div>
                <div class="perf-value" style="color: {throughput_color};">{tpm}</div>
                <div class="perf-label">Tests Per Minute</div>
                <div class="perf-rating">{throughput_rating}</div>
            </div>
            
            <div class="perf-card">
                <div class="perf-icon">⏱️</div>
                <div class="perf-value">{perf['avg_execution_time']*1000:.0f}ms</div>
                <div class="perf-label">Avg Response Time</div>
                <div class="perf-rating">{'Fast' if perf['avg_execution_time'] < 1 else ('Normal' if perf['avg_execution_time'] < 3 else 'Slow')}</div>
            </div>
            
            <div class="perf-card">
                <div class="perf-icon">📊</div>
                <div class="perf-value">{s['total']}</div>
                <div class="perf-label">Total Iterations</div>
                <div class="perf-rating">In {s['duration_minutes']} min</div>
            </div>
            
            <div class="perf-card">
                <div class="perf-icon">🎯</div>
                <div class="perf-value">{s['pass_rate']}%</div>
                <div class="perf-label">Success Rate</div>
                <div class="perf-rating">{'Stable' if s['pass_rate'] >= 95 else ('Good' if s['pass_rate'] >= 80 else 'Needs Work')}</div>
            </div>
        </div>
        
        <div class="stats-table" style="margin-top: 24px;">
            <h3>🔍 Detailed Performance Metrics</h3>
            <table>
                <tr><th>Metric</th><th>Value</th><th>Assessment</th></tr>
                <tr>
                    <td>Minimum Response Time</td>
                    <td>{perf['min_execution_time']*1000:.0f}ms</td>
                    <td class="assessment {'good' if perf['min_execution_time'] < 0.5 else 'warning'}">
                        {'✅ Excellent' if perf['min_execution_time'] < 0.5 else '⚠️ Could be faster'}
                    </td>
                </tr>
                <tr>
                    <td>Average Response Time</td>
                    <td>{perf['avg_execution_time']*1000:.0f}ms</td>
                    <td class="assessment {'good' if perf['avg_execution_time'] < 1 else 'warning'}">
                        {'✅ Fast' if perf['avg_execution_time'] < 1 else '⚠️ Room for improvement'}
                    </td>
                </tr>
                <tr>
                    <td>Maximum Response Time</td>
                    <td>{perf['max_execution_time']*1000:.0f}ms</td>
                    <td class="assessment {'good' if perf['max_execution_time'] < 2 else 'warning'}">
                        {'✅ Acceptable' if perf['max_execution_time'] < 2 else '⚠️ Spikes detected'}
                    </td>
                </tr>
                <tr>
                    <td>Response Time Variance</td>
                    <td>{(perf['max_execution_time'] - perf['min_execution_time'])*1000:.0f}ms</td>
                    <td class="assessment {'good' if (perf['max_execution_time'] - perf['min_execution_time']) < 1 else 'warning'}">
                        {'✅ Consistent' if (perf['max_execution_time'] - perf['min_execution_time']) < 1 else '⚠️ Variable'}
                    </td>
                </tr>
            </table>
        </div>
    </div>
</section>'''
    
    def _generate_health_section(self) -> str:
        """Generate system health section"""
        health = self.report_data['health']
        cpu = health.get('cpu', {})
        memory = health.get('memory', {})
        summary = health.get('summary', {})
        
        # CPU metrics
        cpu_mean = cpu.get('mean', 0)
        cpu_max = cpu.get('max', 0)
        cpu_status = 'good' if cpu_max < 80 else ('warning' if cpu_max < 95 else 'critical')
        
        # Memory metrics
        mem_mean = memory.get('mean', 0)
        mem_max = memory.get('max', 0)
        mem_growth = memory.get('growth', 0)
        mem_status = 'good' if mem_max < 7 else ('warning' if mem_max < 8 else 'critical')
        
        return f'''
<section id="health" class="health-section" style="display:none;">
    <div class="container">
        <h2>💚 System Health</h2>
        
        <div class="health-status-banner {'passed' if health['is_healthy'] else 'failed'}">
            <span class="health-icon">{'✅' if health['is_healthy'] else '❌'}</span>
            <span>System is {'HEALTHY' if health['is_healthy'] else 'UNHEALTHY'}</span>
            <span class="alert-count">({health['alert_count']} alerts)</span>
        </div>
        
        <div class="health-grid">
            <div class="health-card {cpu_status}">
                <h4>🖥️ CPU Usage</h4>
                <div class="health-meter">
                    <div class="meter-fill" style="width: {cpu_mean}%; background: {'var(--success)' if cpu_status == 'good' else ('var(--warning)' if cpu_status == 'warning' else 'var(--fail)')}"></div>
                </div>
                <div class="health-stats">
                    <div><span>Average:</span> <strong>{cpu_mean:.1f}%</strong></div>
                    <div><span>Maximum:</span> <strong>{cpu_max:.1f}%</strong></div>
                </div>
            </div>
            
            <div class="health-card {mem_status}">
                <h4>💾 Memory Usage</h4>
                <div class="health-meter">
                    <div class="meter-fill" style="width: {(mem_mean / 8) * 100:.0f}%; background: {'var(--success)' if mem_status == 'good' else ('var(--warning)' if mem_status == 'warning' else 'var(--fail)')}"></div>
                </div>
                <div class="health-stats">
                    <div><span>Average:</span> <strong>{mem_mean:.2f} GB</strong></div>
                    <div><span>Maximum:</span> <strong>{mem_max:.2f} GB</strong></div>
                    <div><span>Growth:</span> <strong>{mem_growth*1024:.1f} MB</strong></div>
                </div>
            </div>
            
            <div class="health-card">
                <h4>📊 Resource Summary</h4>
                <div class="health-stats">
                    <div><span>Duration:</span> <strong>{summary.get('duration_seconds', 0)}s</strong></div>
                    <div><span>Samples:</span> <strong>{summary.get('samples_collected', 0)}</strong></div>
                    <div><span>Threads:</span> <strong>{summary.get('threads', {}).get('max', 0)}</strong></div>
                    <div><span>File Descriptors:</span> <strong>{summary.get('file_descriptors', {}).get('max', 0)}</strong></div>
                </div>
            </div>
        </div>
    </div>
</section>'''
    
    def _generate_alerts_section(self) -> str:
        """Generate alerts section"""
        health = self.report_data['health']
        alerts = health.get('alerts', [])
        
        if not alerts:
            return f'''
<section id="alerts" class="alerts-section" style="display:none;">
    <div class="container">
        <h2>🚨 Alerts</h2>
        <div class="no-alerts">
            <span class="no-alerts-icon">✅</span>
            <h3>No Alerts</h3>
            <p>No alerts were triggered during this endurance test run.</p>
        </div>
    </div>
</section>'''
        
        # Group alerts by type
        alert_groups = {}
        for alert in alerts:
            alert_type = alert.get('type', 'UNKNOWN')
            if alert_type not in alert_groups:
                alert_groups[alert_type] = []
            alert_groups[alert_type].append(alert)
        
        alerts_html = ''
        for alert_type, group_alerts in alert_groups.items():
            icon = self._get_alert_icon(alert_type)
            alerts_html += f'''
            <div class="alert-group">
                <div class="alert-group-header">
                    <span class="alert-type-icon">{icon}</span>
                    <span class="alert-type-name">{alert_type.replace('_', ' ')}</span>
                    <span class="alert-count-badge">{len(group_alerts)}</span>
                </div>
                <div class="alert-list">
'''
            for alert in group_alerts[:10]:  # Limit to 10 per group
                alerts_html += f'''
                    <div class="alert-item">
                        <span class="alert-message">{self._sanitize_html(alert.get('message', 'No message'))}</span>
                        <span class="alert-time">{alert.get('timestamp', 'Unknown time')}</span>
                    </div>
'''
            if len(group_alerts) > 10:
                alerts_html += f'<div class="alert-more">...and {len(group_alerts) - 10} more</div>'
            alerts_html += '</div></div>'
        
        return f'''
<section id="alerts" class="alerts-section" style="display:none;">
    <div class="container">
        <h2>🚨 Alerts ({len(alerts)} total)</h2>
        <div class="alerts-container">
            {alerts_html}
        </div>
    </div>
</section>'''
    
    def _get_alert_icon(self, alert_type: str) -> str:
        """Get icon for alert type"""
        icons = {
            'HIGH_MEMORY': '💾',
            'HIGH_CPU': '🖥️',
            'MEMORY_LEAK': '🔴',
            'TIMEOUT': '⏰',
            'CONNECTION': '🔌',
            'ERROR': '❌',
        }
        return icons.get(alert_type, '⚠️')
    
    def _generate_css(self) -> str:
        """Override CSS to add endurance-specific styles"""
        base_css = super()._generate_css()
        
        endurance_css = '''
        .status-banner {
            display: flex;
            align-items: center;
            gap: 20px;
            padding: 24px;
            border-radius: 12px;
            margin-bottom: 24px;
            background: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .status-banner.passed { border-left: 6px solid var(--success); }
        .status-banner.warning { border-left: 6px solid var(--warning); }
        .status-banner.failed { border-left: 6px solid var(--fail); }
        .status-icon { font-size: 48px; }
        .status-info { flex: 1; }
        .status-title { font-size: 24px; font-weight: 700; }
        .status-subtitle { color: var(--text-gray); }
        .health-badge {
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: 600;
        }
        .health-badge.passed { background: rgba(16, 185, 129, 0.15); color: var(--success); }
        .health-badge.failed { background: rgba(239, 68, 68, 0.15); color: var(--fail); }
        
        .performance-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 24px;
        }
        .perf-card {
            background: white;
            padding: 24px;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .perf-icon { font-size: 36px; margin-bottom: 12px; }
        .perf-value { font-size: 32px; font-weight: 700; }
        .perf-label { color: var(--text-gray); margin-top: 8px; }
        .perf-rating { 
            margin-top: 8px; 
            padding: 4px 12px; 
            background: var(--bg-light); 
            border-radius: 12px; 
            font-size: 12px;
            display: inline-block;
        }
        
        .health-status-banner {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            padding: 16px;
            border-radius: 8px;
            margin-bottom: 24px;
            font-weight: 600;
            font-size: 18px;
        }
        .health-status-banner.passed { background: rgba(16, 185, 129, 0.15); color: var(--success); }
        .health-status-banner.failed { background: rgba(239, 68, 68, 0.15); color: var(--fail); }
        
        .health-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
        }
        .health-card {
            background: white;
            padding: 24px;
            border-radius: 12px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .health-card h4 { margin-bottom: 16px; }
        .health-meter {
            height: 12px;
            background: var(--bg-light);
            border-radius: 6px;
            overflow: hidden;
            margin-bottom: 16px;
        }
        .meter-fill {
            height: 100%;
            border-radius: 6px;
            transition: width 0.5s ease;
        }
        .health-stats { display: flex; flex-direction: column; gap: 8px; }
        .health-stats > div {
            display: flex;
            justify-content: space-between;
            padding: 8px;
            background: var(--bg-light);
            border-radius: 4px;
        }
        
        .no-alerts {
            text-align: center;
            padding: 60px;
            background: rgba(16, 185, 129, 0.05);
            border-radius: 12px;
        }
        .no-alerts-icon { font-size: 64px; display: block; margin-bottom: 16px; }
        
        .alerts-container { display: flex; flex-direction: column; gap: 20px; }
        .alert-group {
            background: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .alert-group-header {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 16px 20px;
            background: var(--bg-light);
            font-weight: 600;
        }
        .alert-type-icon { font-size: 24px; }
        .alert-count-badge {
            margin-left: auto;
            background: var(--fail);
            color: white;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
        }
        .alert-list { padding: 0 20px; }
        .alert-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid var(--border);
        }
        .alert-item:last-child { border-bottom: none; }
        .alert-message { flex: 1; }
        .alert-time { color: var(--text-gray); font-size: 12px; }
        .alert-more { padding: 12px; color: var(--text-gray); font-style: italic; }
        '''
        
        return base_css.replace('</style>', endurance_css + '</style>')


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description='Generate enhanced Endurance HTML report')
    parser.add_argument('--input', required=True, help='Input endurance JSON file')
    parser.add_argument('--output', required=True, help='Output HTML file path')
    parser.add_argument('--title', default='Endurance Test Report', help='Report title')
    
    args = parser.parse_args()
    
    generator = EnduranceReportGenerator(
        json_path=args.input,
        output_html_path=args.output,
        title=args.title
    )
    
    success = generator.generate_report()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
