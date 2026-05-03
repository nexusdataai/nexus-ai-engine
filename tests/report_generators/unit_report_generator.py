#!/usr/bin/env python3
"""
Unit Test Report Generator
Generates professional HTML reports from pytest JSON output
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
    # Running as script, add parent to path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from base_report_generator import BaseReportGenerator


class UnitTestReportGenerator(BaseReportGenerator):
    """Generate enhanced HTML reports from pytest JSON output"""
    
    def __init__(self, pytest_json_path: str, output_html_path: str, title: str = "Unit Test Report"):
        super().__init__(pytest_json_path, output_html_path, title)
        self.pytest_data = {}
        self.test_hierarchy = {}
        
    def load_data(self):
        """Load pytest JSON output"""
        try:
            with open(self.input_path, 'r') as f:
                self.pytest_data = json.load(f)
            print(f"✅ Loaded test results from {self.input_path}")
            return True
        except Exception as e:
            print(f"❌ Error loading pytest JSON: {e}")
            return False
    
    def parse_data(self):
        """Parse pytest data into report structure"""
        # Get summary
        summary = self.pytest_data.get('summary', {})
        
        # Build test hierarchy from collectors
        collectors = self.pytest_data.get('collectors', [])
        tests = self.pytest_data.get('tests', [])
        
        # Parse test hierarchy
        test_tree = self._build_test_tree(collectors, tests)
        
        # Calculate statistics
        total_tests = summary.get('total', summary.get('collected', 0))
        passed = len([t for t in tests if t.get('outcome') == 'passed'])
        failed = len([t for t in tests if t.get('outcome') == 'failed'])
        skipped = len([t for t in tests if t.get('outcome') == 'skipped'])
        error = len([t for t in tests if t.get('outcome') == 'error'])
        
        # Get durations
        durations = [t.get('duration', 0) for t in tests if t.get('duration')]
        total_duration = sum(durations)
        avg_duration = total_duration / len(durations) if durations else 0
        
        # Build report data
        self.report_data = {
            'metadata': {
                'title': self.title,
                'subtitle': 'Unit Test Results',
                'icon': '🧪',
                'generated_at': datetime.now().strftime('%B %d, %Y %H:%M:%S'),
                'timestamp': datetime.now().isoformat(),
            },
            'summary': {
                'total': total_tests,
                'passed': passed,
                'failed': failed,
                'skipped': skipped,
                'error': error,
                'pass_rate': round((passed / total_tests * 100) if total_tests > 0 else 0, 1),
                'total_duration': total_duration,
                'average_duration': avg_duration,
                'fastest_test': min(durations) if durations else 0,
                'slowest_test': max(durations) if durations else 0
            },
            'test_tree': test_tree,
            'failed_tests': [t for t in tests if t.get('outcome') == 'failed'],
            'navigation_tabs': [
                ('overview', '📊 Overview'),
                ('tests', '🧪 Tests'),
                ('failed', '❌ Failed'),
                ('analytics', '📈 Analytics')
            ]
        }
        
        print(f"✅ Parsed {total_tests} tests: {passed} passed, {failed} failed, {skipped} skipped")
        return True
    
    def _build_test_tree(self, collectors: List[Dict], tests: List[Dict]) -> Dict:
        """Build hierarchical test structure from pytest collectors"""
        tree = {}
        
        # Group tests by module
        for test in tests:
            nodeid = test.get('nodeid', '')
            if not nodeid:
                continue
            
            # Parse nodeid: path/to/file.py::Class::test_function
            parts = nodeid.split('::')
            if not parts:
                continue
            
            file_path = parts[0]
            
            # Get module name from file path
            module = file_path.replace('/', '.').replace('.py', '')
            
            if module not in tree:
                tree[module] = {
                    'name': module,
                    'file_path': file_path,
                    'classes': {},
                    'tests': [],
                    'stats': {'total': 0, 'passed': 0, 'failed': 0, 'skipped': 0}
                }
            
            # Update module stats
            tree[module]['stats']['total'] += 1
            outcome = test.get('outcome', 'error')
            if outcome in tree[module]['stats']:
                tree[module]['stats'][outcome] += 1
            
            # If there's a class, group by class
            if len(parts) > 2:
                class_name = parts[1]
                if class_name not in tree[module]['classes']:
                    tree[module]['classes'][class_name] = {
                        'name': class_name,
                        'tests': [],
                        'stats': {'total': 0, 'passed': 0, 'failed': 0, 'skipped': 0}
                    }
                
                tree[module]['classes'][class_name]['tests'].append(test)
                tree[module]['classes'][class_name]['stats']['total'] += 1
                if outcome in tree[module]['classes'][class_name]['stats']:
                    tree[module]['classes'][class_name]['stats'][outcome] += 1
            else:
                # Top-level test function
                tree[module]['tests'].append(test)
        
        return tree
    
    def _generate_content_sections(self) -> str:
        """Generate unit test-specific content sections"""
        return (
            self._generate_overview_section() +
            self._generate_tests_section() +
            self._generate_failed_section() +
            self._generate_analytics_section()
        )
    
    def _generate_overview_section(self) -> str:
        """Generate overview section with summary and charts"""
        s = self.report_data['summary']
        
        # Summary cards
        cards_data = [
            {'type': 'total', 'icon': '📊', 'value': s['total'], 'label': 'Total Tests'},
            {'type': 'passed', 'icon': '✅', 'value': s['passed'], 'label': 'Passed'},
            {'type': 'failed', 'icon': '❌', 'value': s['failed'], 'label': 'Failed'},
            {'type': 'skipped', 'icon': '⏭️', 'value': s['skipped'], 'label': 'Skipped'}
        ]
        
        # Pie chart data
        pie_data = {
            'Passed': s['passed'],
            'Failed': s['failed'],
            'Skipped': s['skipped'],
            'Error': s['error']
        }
        
        # Bar chart data - tests by module
        modules_data = []
        for module_name, module_data in self.report_data['test_tree'].items():
            short_name = module_name.split('.')[-1] if '.' in module_name else module_name
            modules_data.append({
                'name': short_name,
                'passed': module_data['stats']['passed'],
                'failed': module_data['stats']['failed'],
                'skipped': module_data['stats']['skipped']
            })
        
        # Sort by total tests
        modules_data.sort(key=lambda x: x['passed'] + x['failed'] + x['skipped'], reverse=True)
        modules_data = modules_data[:10]  # Top 10 modules
        
        labels = [m['name'] for m in modules_data]
        datasets = [
            {
                'label': 'Passed',
                'data': [m['passed'] for m in modules_data],
                'backgroundColor': 'rgb(16, 185, 129)'
            },
            {
                'label': 'Failed',
                'data': [m['failed'] for m in modules_data],
                'backgroundColor': 'rgb(239, 68, 68)'
            },
            {
                'label': 'Skipped',
                'data': [m['skipped'] for m in modules_data],
                'backgroundColor': 'rgb(156, 163, 175)'
            }
        ]
        
        return f'''
<section id="overview" class="overview-section">
    <div class="container">
        <h2>📊 Test Results Overview</h2>
        
        {self._generate_summary_cards(cards_data)}
        
        <div class="charts-grid">
            {self._generate_pie_chart('statusPieChart', 'Status Distribution', pie_data)}
            {self._generate_bar_chart('modulesBarChart', 'Tests by Module (Top 10)', labels, datasets)}
        </div>
        
        <div class="stats-table">
            <h3>Test Statistics</h3>
            <table>
                <tr><th>Metric</th><th>Value</th></tr>
                <tr><td>Total Tests</td><td>{s['total']}</td></tr>
                <tr><td>Pass Rate</td><td><strong>{s['pass_rate']}%</strong></td></tr>
                <tr><td>Execution Time</td><td>{self._format_duration(s['total_duration'])}</td></tr>
                <tr><td>Average Test Time</td><td>{self._format_duration(s['average_duration'])}</td></tr>
                <tr><td>Fastest Test</td><td>{self._format_duration(s['fastest_test'])}</td></tr>
                <tr><td>Slowest Test</td><td>{self._format_duration(s['slowest_test'])}</td></tr>
                <tr><td>Total Modules</td><td>{len(self.report_data['test_tree'])}</td></tr>
            </table>
        </div>
    </div>
</section>'''
    
    def _generate_tests_section(self) -> str:
        """Generate tests section with hierarchical view"""
        html = '''
<section id="tests" class="tests-section" style="display:none;">
    <div class="container">
        <h2>🧪 Test Details</h2>
        
        <div class="controls">
            <input type="text" id="searchBox" placeholder="🔍 Search tests..." onkeyup="filterItems('searchBox', '.item-card')">
            <select id="statusFilter" onchange="filterByStatus('statusFilter', '.item-card')">
                <option value="all">All Status</option>
                <option value="passed">✅ Passed Only</option>
                <option value="failed">❌ Failed Only</option>
                <option value="skipped">⏭️ Skipped Only</option>
            </select>
            <button onclick="expandAll()">Expand All</button>
            <button onclick="collapseAll()">Collapse All</button>
            <button onclick="expandAllFailed()">Expand Failed</button>
        </div>
        
        <div class="tests-list">
'''
        
        # Generate module cards
        for module_name, module_data in sorted(self.report_data['test_tree'].items()):
            html += self._generate_module_card(module_name, module_data)
        
        html += '''
        </div>
    </div>
</section>'''
        
        return html
    
    def _generate_module_card(self, module_name: str, module_data: Dict) -> str:
        """Generate card for a module"""
        stats = module_data['stats']
        status = 'failed' if stats['failed'] > 0 else 'passed'
        pass_rate = round((stats['passed'] / stats['total'] * 100) if stats['total'] > 0 else 0, 1)
        
        # Generate content: classes and top-level tests
        content_html = ''
        
        # Classes
        for class_name, class_data in sorted(module_data['classes'].items()):
            content_html += self._generate_class_section(class_name, class_data)
        
        # Top-level tests
        if module_data['tests']:
            content_html += '<div style="margin-top: 16px;"><h4>Module-level Tests</h4>'
            for test in module_data['tests']:
                content_html += self._generate_test_item(test)
            content_html += '</div>'
        
        return f'''
<div class="item-card {status}" id="{module_name.replace('.', '-')}">
    <div class="item-header" onclick="toggleItem('{module_name.replace('.', '-')}')">
        <div class="item-title">
            <span class="expand-icon">▶</span>
            <h3>{module_name}</h3>
        </div>
        <div class="item-stats">
            <span class="count">{stats['total']} tests</span>
            <span class="pass-rate">{pass_rate}%</span>
            <span class="status-indicator {status}">●</span>
        </div>
    </div>
    <div class="item-body" id="{module_name.replace('.', '-')}-body">
        <div class="description">📁 {module_data['file_path']}</div>
        {content_html}
    </div>
</div>'''
    
    def _generate_class_section(self, class_name: str, class_data: Dict) -> str:
        """Generate section for a test class"""
        stats = class_data['stats']
        status = 'failed' if stats['failed'] > 0 else 'passed'
        
        tests_html = ''
        for test in class_data['tests']:
            tests_html += self._generate_test_item(test)
        
        return f'''
<div style="margin: 16px 0; padding: 16px; background: var(--bg-light); border-radius: 8px; border-left: 3px solid var(--{"fail" if status == "failed" else "success"});">
    <h4 style="margin-bottom: 12px;">📦 {class_name} <span style="color: var(--text-gray); font-size: 14px; font-weight: normal;">({stats['passed']}/{stats['total']} passed)</span></h4>
    <div>
        {tests_html}
    </div>
</div>'''
    
    def _generate_test_item(self, test: Dict) -> str:
        """Generate item for a single test"""
        outcome = test.get('outcome', 'error')
        nodeid = test.get('nodeid', '')
        duration = test.get('duration', 0)
        
        # Extract test name from nodeid
        test_name = nodeid.split('::')[-1] if '::' in nodeid else nodeid
        
        # Get status icon
        status_icon = self._get_status_icon(outcome)
        
        # Build error details if failed
        error_html = ''
        if outcome == 'failed':
            call = test.get('call', {})
            longrepr = call.get('longrepr', '')
            if longrepr:
                error_html = f'''
<div class="error-details">
    <div class="error-header">❌ Error Details</div>
    <pre class="error-message">{self._sanitize_html(longrepr)}</pre>
</div>'''
        
        return f'''
<div class="item-card {outcome}" style="margin: 8px 0;">
    <div style="padding: 12px; display: flex; justify-content: space-between; align-items: center;">
        <div style="flex: 1; display: flex; align-items: center; gap: 12px;">
            <span style="font-size: 20px;">{status_icon}</span>
            <span>{test_name}</span>
        </div>
        <div style="display: flex; gap: 12px; align-items: center;">
            <span class="duration">{self._format_duration(duration)}</span>
            <span class="status-badge {outcome}">{outcome}</span>
        </div>
    </div>
    {error_html}
</div>'''
    
    def _generate_failed_section(self) -> str:
        """Generate failed tests section"""
        failed_tests = self.report_data['failed_tests']
        
        html = f'''
<section id="failed" class="failed-section" style="display:none;">
    <div class="container">
        <h2>❌ Failed Tests ({len(failed_tests)})</h2>
'''
        
        if not failed_tests:
            html += '<p>🎉 No failed tests! All tests passed successfully.</p>'
        else:
            for test in failed_tests:
                html += self._generate_failed_test_card(test)
        
        html += '''
    </div>
</section>'''
        
        return html
    
    def _generate_failed_test_card(self, test: Dict) -> str:
        """Generate detailed card for a failed test"""
        nodeid = test.get('nodeid', '')
        duration = test.get('duration', 0)
        call = test.get('call', {})
        longrepr = call.get('longrepr', 'No error details available')
        
        return f'''
<div class="item-card failed" style="margin-bottom: 20px;">
    <div class="item-header">
        <div class="item-title">
            <h3>❌ {nodeid}</h3>
        </div>
        <div class="item-stats">
            <span class="duration">{self._format_duration(duration)}</span>
        </div>
    </div>
    <div class="item-body" style="display: block;">
        <div class="error-details">
            <div class="error-header">Error Traceback</div>
            <pre class="error-message">{self._sanitize_html(longrepr)}</pre>
        </div>
    </div>
</div>'''
    
    def _generate_analytics_section(self) -> str:
        """Generate analytics section with performance insights"""
        # Get all tests sorted by duration
        all_tests = self.pytest_data.get('tests', [])
        tests_with_duration = [(t.get('nodeid', ''), t.get('duration', 0)) for t in all_tests if t.get('duration')]
        tests_with_duration.sort(key=lambda x: x[1], reverse=True)
        slowest_tests = tests_with_duration[:20]
        
        html = '''
<section id="analytics" class="analytics-section" style="display:none;">
    <div class="container">
        <h2>📈 Performance Analytics</h2>
        
        <div class="stats-table">
            <h3>Slowest Tests (Top 20)</h3>
            <table>
                <tr><th>Test</th><th>Duration</th></tr>
'''
        
        for test_name, duration in slowest_tests:
            html += f'<tr><td>{test_name}</td><td>{self._format_duration(duration)}</td></tr>'
        
        html += '''
            </table>
        </div>
    </div>
</section>'''
        
        return html


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description='Generate enhanced unit test HTML report')
    parser.add_argument('--input', required=True, help='Input pytest JSON file')
    parser.add_argument('--output', required=True, help='Output HTML file path')
    parser.add_argument('--title', default='Unit Test Report', help='Report title')
    
    args = parser.parse_args()
    
    generator = UnitTestReportGenerator(
        pytest_json_path=args.input,
        output_html_path=args.output,
        title=args.title
    )
    
    success = generator.generate_report()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

