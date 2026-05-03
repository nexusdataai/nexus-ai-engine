#!/usr/bin/env python3
"""
Integration Test Report Generator
Generates professional HTML reports from integration test JSON output
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


class IntegrationTestReportGenerator(BaseReportGenerator):
    """Generate enhanced HTML reports from integration test JSON output"""
    
    def __init__(self, pytest_json_path: str, output_html_path: str, title: str = "Integration Test Report"):
        super().__init__(pytest_json_path, output_html_path, title)
        self.pytest_data = {}
        self.test_hierarchy = {}
        
    def load_data(self):
        """Load pytest JSON output"""
        try:
            with open(self.input_path, 'r') as f:
                self.pytest_data = json.load(f)
            print(f"✅ Loaded integration test results from {self.input_path}")
            return True
        except Exception as e:
            print(f"❌ Error loading pytest JSON: {e}")
            return False
    
    def parse_data(self):
        """Parse pytest data into report structure"""
        summary = self.pytest_data.get('summary', {})
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
        
        # Categorize by test type
        api_tests = [t for t in tests if '/api/' in t.get('nodeid', '')]
        mcp_tests = [t for t in tests if '/mcp/' in t.get('nodeid', '')]
        service_tests = [t for t in tests if '/services/' in t.get('nodeid', '')]
        workflow_tests = [t for t in tests if '/workflows/' in t.get('nodeid', '')]
        performance_tests = [t for t in tests if '/performance/' in t.get('nodeid', '')]
        
        # Build report data
        self.report_data = {
            'metadata': {
                'title': self.title,
                'subtitle': 'End-to-End Integration Test Results',
                'icon': '🔗',
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
            'categories': {
                'api_tests': len(api_tests),
                'mcp_tests': len(mcp_tests),
                'service_tests': len(service_tests),
                'workflow_tests': len(workflow_tests),
                'performance_tests': len(performance_tests)
            },
            'test_tree': test_tree,
            'failed_tests': [t for t in tests if t.get('outcome') == 'failed'],
            'navigation_tabs': [
                ('overview', '📊 Overview'),
                ('tests', '🧪 Tests'),
                ('categories', '📁 Categories'),
                ('failed', '❌ Failed'),
                ('analytics', '📈 Analytics')
            ]
        }
        
        print(f"✅ Parsed {total_tests} integration tests: {passed} passed, {failed} failed, {skipped} skipped")
        return True
    
    def _build_test_tree(self, collectors: List[Dict], tests: List[Dict]) -> Dict:
        """Build hierarchical test tree from collectors and tests"""
        tree = {}
        
        # Group tests by module
        for test in tests:
            nodeid = test.get('nodeid', '')
            parts = nodeid.split('::')
            
            if len(parts) < 2:
                continue
            
            file_path = parts[0]
            test_class = parts[1] if len(parts) > 2 else 'General'
            test_name = parts[-1]
            
            # Extract module path
            module_parts = file_path.replace('tests/integration/python/', '').split('/')
            category = module_parts[0] if module_parts else 'other'
            file_name = module_parts[-1] if module_parts else file_path
            
            # Initialize category
            if category not in tree:
                tree[category] = {
                    'name': category.replace('_', ' ').title(),
                    'files': {},
                    'total': 0,
                    'passed': 0,
                    'failed': 0,
                    'skipped': 0
                }
            
            # Initialize file
            if file_name not in tree[category]['files']:
                tree[category]['files'][file_name] = {
                    'classes': {},
                    'total': 0,
                    'passed': 0,
                    'failed': 0,
                    'skipped': 0
                }
            
            # Initialize class
            if test_class not in tree[category]['files'][file_name]['classes']:
                tree[category]['files'][file_name]['classes'][test_class] = {
                    'tests': [],
                    'total': 0,
                    'passed': 0,
                    'failed': 0,
                    'skipped': 0
                }
            
            # Add test
            test_info = {
                'name': test_name,
                'outcome': test.get('outcome', 'unknown'),
                'duration': test.get('duration', 0),
                'nodeid': nodeid,
                'call': test.get('call', {}),
                'longrepr': test.get('longrepr', ''),
            }
            
            tree[category]['files'][file_name]['classes'][test_class]['tests'].append(test_info)
            
            # Update counts
            outcome = test.get('outcome', 'unknown')
            if outcome == 'passed':
                tree[category]['passed'] += 1
                tree[category]['files'][file_name]['passed'] += 1
                tree[category]['files'][file_name]['classes'][test_class]['passed'] += 1
            elif outcome == 'failed':
                tree[category]['failed'] += 1
                tree[category]['files'][file_name]['failed'] += 1
                tree[category]['files'][file_name]['classes'][test_class]['failed'] += 1
            elif outcome == 'skipped':
                tree[category]['skipped'] += 1
                tree[category]['files'][file_name]['skipped'] += 1
                tree[category]['files'][file_name]['classes'][test_class]['skipped'] += 1
            
            tree[category]['total'] += 1
            tree[category]['files'][file_name]['total'] += 1
            tree[category]['files'][file_name]['classes'][test_class]['total'] += 1
        
        return tree
    
    def _generate_content_sections(self) -> str:
        """Generate integration test-specific content sections"""
        return f'''
    <div class="container">
        <!-- Overview Section -->
        <section id="overview" style="display: block;">
            <h2>📊 Test Summary</h2>
            {self._generate_summary_section()}
            
            <h2>📈 Category Breakdown</h2>
            {self._generate_category_breakdown()}
            
            <h2>📊 Visual Analytics</h2>
            <div class="charts-grid">
                {self._generate_outcome_chart()}
                {self._generate_category_chart()}
            </div>
        </section>
        
        <!-- Tests Section -->
        <section id="tests" style="display: none;">
            <h2>🧪 Integration Tests by Category</h2>
            {self._generate_tests_section()}
        </section>
        
        <!-- Categories Section -->
        <section id="categories" style="display: none;">
            <h2>📁 Test Categories</h2>
            {self._generate_categories_detail()}
        </section>
        
        <!-- Failed Tests Section -->
        <section id="failed" style="display: none;">
            <h2>❌ Failed Tests</h2>
            {self._generate_failed_tests_section()}
        </section>
        
        <!-- Analytics Section -->
        <section id="analytics" style="display: none;">
            <h2>📈 Test Analytics</h2>
            {self._generate_analytics_section()}
        </section>
    </div>'''
    
    def _generate_summary_section(self) -> str:
        """Generate summary cards"""
        summary = self.report_data['summary']
        
        cards = [
            {
                'type': 'total',
                'icon': '📊',
                'value': summary['total'],
                'label': 'Total Tests'
            },
            {
                'type': 'passed',
                'icon': '✅',
                'value': summary['passed'],
                'label': 'Passed'
            },
            {
                'type': 'failed',
                'icon': '❌',
                'value': summary['failed'],
                'label': 'Failed'
            },
            {
                'type': 'skipped',
                'icon': '○',
                'value': summary['skipped'],
                'label': 'Skipped'
            },
            {
                'type': 'total',
                'icon': '⏱',
                'value': f"{summary['total_duration']:.1f}s",
                'label': 'Total Duration'
            }
        ]
        
        return self._generate_summary_cards(cards)
    
    def _generate_category_breakdown(self) -> str:
        """Generate category breakdown table"""
        categories = self.report_data['categories']
        
        html = '<div class="stats-table"><table>'
        html += '<thead><tr>'
        html += '<th>Category</th><th>Tests</th>'
        html += '</tr></thead><tbody>'
        
        for category, count in categories.items():
            if count > 0:
                category_name = category.replace('_tests', '').replace('_', ' ').title()
                html += f'<tr><td>{category_name}</td><td>{count}</td></tr>'
        
        html += '</tbody></table></div>'
        return html
    
    def _generate_tests_section(self) -> str:
        """Generate expandable test hierarchy"""
        tree = self.report_data['test_tree']
        html = '<div class="controls">'
        html += '<button onclick="expandAll()">Expand All</button>'
        html += '<button onclick="collapseAll()">Collapse All</button>'
        html += '<button onclick="expandAllFailed()">Expand Failed Only</button>'
        html += '</div>'
        
        for category_name, category_data in sorted(tree.items()):
            html += self._generate_category_section(category_name, category_data)
        
        return html
    
    def _generate_category_section(self, category_name: str, category_data: Dict) -> str:
        """Generate category section with files and tests"""
        cat_id = category_name.replace('/', '_').replace(' ', '_')
        status = 'passed' if category_data['failed'] == 0 else 'failed'
        pass_rate = round((category_data['passed'] / category_data['total'] * 100) if category_data['total'] > 0 else 0, 1)
        
        html = f'''
        <div class="item-card {status}" id="cat-{cat_id}">
            <div class="item-header" onclick="toggleItem('cat-{cat_id}')">
                <div class="item-title">
                    <span class="expand-icon">▶</span>
                    <h3>📁 {category_data['name']}</h3>
                </div>
                <div class="item-stats">
                    <span class="count">{category_data['total']} tests</span>
                    <span class="pass-rate">{pass_rate}%</span>
                    <span class="status-indicator {status}">{self._get_status_icon(status)}</span>
                </div>
            </div>
            <div class="item-body" id="cat-{cat_id}-body">'''
        
        # Add files
        for file_name, file_data in sorted(category_data['files'].items()):
            html += self._generate_file_section(cat_id, file_name, file_data)
        
        html += '</div></div>'
        return html
    
    def _generate_file_section(self, category_id: str, file_name: str, file_data: Dict) -> str:
        """Generate file section with test classes"""
        file_id = f"{category_id}_{file_name.replace('.py', '').replace('/', '_')}"
        status = 'passed' if file_data['failed'] == 0 else 'failed'
        
        html = f'''
        <div class="item-card {status}" id="file-{file_id}" style="margin: 16px 0;">
            <div class="item-header" onclick="toggleItem('file-{file_id}')">
                <div class="item-title">
                    <span class="expand-icon">▶</span>
                    <h4>📄 {file_name}</h4>
                </div>
                <div class="item-stats">
                    <span class="count">{file_data['passed']}/{file_data['total']}</span>
                </div>
            </div>
            <div class="item-body" id="file-{file_id}-body">'''
        
        # Add test classes
        for class_name, class_data in sorted(file_data['classes'].items()):
            html += self._generate_class_tests(file_id, class_name, class_data)
        
        html += '</div></div>'
        return html
    
    def _generate_class_tests(self, file_id: str, class_name: str, class_data: Dict) -> str:
        """Generate individual tests within a class"""
        html = f'<h4 style="margin: 16px 0 8px 0; color: #667eea;">📦 {class_name}</h4>'
        
        for test in class_data['tests']:
            test_id = f"{file_id}_{test['name'].replace('[', '_').replace(']', '_')}"
            outcome = test['outcome']
            duration = test.get('duration', 0)
            
            html += f'''
            <div class="item-card {outcome}" id="test-{test_id}" style="margin: 8px 0;">
                <div class="item-header" onclick="toggleItem('test-{test_id}')">
                    <div class="item-title">
                        <span class="status-indicator {outcome}">{self._get_status_icon(outcome)}</span>
                        <span>{test['name']}</span>
                    </div>
                    <div class="item-stats">
                        <span class="duration">{duration:.3f}s</span>
                    </div>
                </div>
                <div class="item-body" id="test-{test_id}-body">'''
            
            if outcome == 'failed':
                html += self._generate_error_details(test)
            else:
                html += f'<p>✅ Test passed in {duration:.3f}s</p>'
            
            html += '</div></div>'
        
        return html
    
    def _generate_error_details(self, test: Dict) -> str:
        """Generate error details for failed tests"""
        longrepr = test.get('longrepr', '')
        call_info = test.get('call', {})
        
        html = '<div class="error-details">'
        html += '<div class="error-header">❌ Test Failure Details</div>'
        
        if longrepr:
            html += f'<div class="error-message">{self._sanitize_html(str(longrepr))}</div>'
        elif call_info:
            crash = call_info.get('crash', {})
            if crash:
                html += f'<div class="error-message">{self._sanitize_html(str(crash))}</div>'
        
        html += '</div>'
        return html
    
    def _generate_categories_detail(self) -> str:
        """Generate detailed category statistics"""
        categories = self.report_data['categories']
        
        html = '<div class="stats-table"><table>'
        html += '<thead><tr>'
        html += '<th>Category</th><th>Type</th><th>Count</th><th>Description</th>'
        html += '</tr></thead><tbody>'
        
        category_info = {
            'api_tests': ('🌐 API Tests', 'REST API endpoint tests'),
            'mcp_tests': ('🔧 MCP Tool Tests', 'MCP tool integration tests'),
            'service_tests': ('⚙️ Service Tests', 'Service layer integration tests'),
            'workflow_tests': ('🔄 Workflow Tests', 'End-to-end workflow tests'),
            'performance_tests': ('⚡ Performance Tests', 'Performance and load tests')
        }
        
        for key, count in categories.items():
            if count > 0:
                name, desc = category_info.get(key, (key.title(), ''))
                html += f'<tr><td>{name}</td><td>Integration</td><td>{count}</td><td>{desc}</td></tr>'
        
        html += '</tbody></table></div>'
        return html
    
    def _generate_failed_tests_section(self) -> str:
        """Generate section showing only failed tests"""
        failed_tests = self.report_data['failed_tests']
        
        if not failed_tests:
            return '<p style="color: #10b981; font-size: 18px; text-align: center; padding: 40px;">🎉 No failed tests! All integration tests passed!</p>'
        
        html = f'<p>Found {len(failed_tests)} failed test(s)</p>'
        html += '<div class="controls">'
        html += '<input type="text" id="failedSearchBox" placeholder="Search failed tests..." onkeyup="filterItems(\'failedSearchBox\', \'.failed-test-card\')">'
        html += '</div>'
        
        for test in failed_tests:
            test_id = f"failed_{test['nodeid'].replace('/', '_').replace('::', '_').replace('[', '_').replace(']', '_')}"
            duration = test.get('duration', 0)
            
            html += f'''
            <div class="item-card failed failed-test-card" id="{test_id}">
                <div class="item-header" onclick="toggleItem('{test_id}')">
                    <div class="item-title">
                        <span class="expand-icon">▶</span>
                        <h4>❌ {test['nodeid']}</h4>
                    </div>
                    <div class="item-stats">
                        <span class="duration">{duration:.3f}s</span>
                    </div>
                </div>
                <div class="item-body" id="{test_id}-body">
                    {self._generate_error_details(test)}
                </div>
            </div>'''
        
        return html
    
    def _generate_analytics_section(self) -> str:
        """Generate analytics section with detailed stats"""
        summary = self.report_data['summary']
        categories = self.report_data['categories']
        
        html = '<div class="stats-table"><h3>📊 Test Statistics</h3><table>'
        html += '<thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>'
        
        html += f'<tr><td>Total Tests</td><td>{summary["total"]}</td></tr>'
        html += f'<tr><td>Pass Rate</td><td>{summary["pass_rate"]}%</td></tr>'
        html += f'<tr><td>Total Duration</td><td>{self._format_duration(summary["total_duration"])}</td></tr>'
        html += f'<tr><td>Average Duration</td><td>{summary["average_duration"]:.3f}s</td></tr>'
        html += f'<tr><td>Fastest Test</td><td>{summary["fastest_test"]:.3f}s</td></tr>'
        html += f'<tr><td>Slowest Test</td><td>{summary["slowest_test"]:.3f}s</td></tr>'
        
        html += '</tbody></table></div>'
        
        # Category details
        html += '<div class="stats-table" style="margin-top: 24px;"><h3>📁 Tests by Category</h3><table>'
        html += '<thead><tr><th>Category</th><th>Count</th><th>Percentage</th></tr></thead><tbody>'
        
        total = summary['total']
        for key, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                percentage = round((count / total * 100) if total > 0 else 0, 1)
                name = key.replace('_tests', '').replace('_', ' ').title()
                html += f'<tr><td>{name}</td><td>{count}</td><td>{percentage}%</td></tr>'
        
        html += '</tbody></table></div>'
        
        return html
    
    def _generate_outcome_chart(self) -> str:
        """Generate pie chart for test outcomes"""
        summary = self.report_data['summary']
        
        data = {
            'Passed': summary['passed'],
            'Failed': summary['failed'],
            'Skipped': summary['skipped'],
            'Error': summary['error']
        }
        
        # Remove zero values
        data = {k: v for k, v in data.items() if v > 0}
        
        return self._generate_pie_chart('outcomeChart', 'Test Outcomes', data)
    
    def _generate_category_chart(self) -> str:
        """Generate bar chart for category breakdown"""
        categories = self.report_data['categories']
        
        labels = []
        values = []
        
        for key, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                name = key.replace('_tests', '').replace('_', ' ').title()
                labels.append(name)
                values.append(count)
        
        datasets = [{
            'label': 'Tests',
            'data': values,
            'backgroundColor': 'rgba(102, 126, 234, 0.8)'
        }]
        
        return self._generate_bar_chart('categoryChart', 'Tests by Category', labels, datasets)


def main():
    parser = argparse.ArgumentParser(description='Generate enhanced integration test HTML report')
    parser.add_argument('--input', '-i', required=True, help='Input pytest JSON file')
    parser.add_argument('--output', '-o', required=True, help='Output HTML file')
    parser.add_argument('--title', '-t', default='Integration Test Report', help='Report title')
    
    args = parser.parse_args()
    
    print(f"🔗 Generating integration test report...")
    print(f"   Input:  {args.input}")
    print(f"   Output: {args.output}")
    print(f"   Title:  {args.title}")
    print()
    
    generator = IntegrationTestReportGenerator(args.input, args.output, args.title)
    
    if generator.generate_report():
        print(f"\n✅ Successfully generated integration test report: {args.output}")
        return 0
    else:
        print(f"\n❌ Failed to generate report")
        return 1


if __name__ == '__main__':
    sys.exit(main())

