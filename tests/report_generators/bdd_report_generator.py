#!/usr/bin/env python3
"""
BDD Test Report Generator
Generates professional HTML reports from behave JSON output
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
    # Running as script, add parent to path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from base_report_generator import BaseReportGenerator


class BDDReportGenerator(BaseReportGenerator):
    """Generate enhanced HTML reports from behave JSON output"""
    
    def __init__(self, behave_json_path: str, output_html_path: str, title: str = "BDD Test Report"):
        super().__init__(behave_json_path, output_html_path, title)
        self.behave_data = []
        
    def load_data(self):
        """Load behave JSON output"""
        try:
            with open(self.input_path, 'r') as f:
                self.behave_data = json.load(f)
            print(f"✅ Loaded {len(self.behave_data)} features from {self.input_path}")
            return True
        except Exception as e:
            print(f"❌ Error loading behave JSON: {e}")
            return False
    
    def parse_data(self):
        """Parse behave data into report structure"""
        features = []
        total_scenarios = 0
        passed_scenarios = 0
        failed_scenarios = 0
        error_scenarios = 0
        skipped_scenarios = 0
        total_steps = 0
        passed_steps = 0
        failed_steps = 0
        skipped_steps = 0
        undefined_steps = 0
        
        total_duration = 0
        scenario_durations = []
        
        for feature_idx, feature_data in enumerate(self.behave_data):
            feature = {
                'id': f'feature-{feature_idx}',
                'name': feature_data.get('name', 'Unknown Feature'),
                'description': feature_data.get('description', ''),
                'tags': [tag.replace('~', '') for tag in feature_data.get('tags', [])],
                'status': 'passed',
                'scenarios': [],
                'passed_count': 0,
                'failed_count': 0,
                'error_count': 0
            }
            
            for element in feature_data.get('elements', []):
                if element.get('type') != 'scenario':
                    continue
                
                total_scenarios += 1
                scenario_duration = 0
                
                scenario = {
                    'id': f'scenario-{feature_idx}-{len(feature["scenarios"])}',
                    'name': element.get('name', 'Unknown Scenario'),
                    'tags': [tag.replace('~', '') for tag in element.get('tags', [])],
                    'status': element.get('status', 'error'),
                    'steps': [],
                    'location': element.get('location', 'unknown'),
                    'duration': 0
                }
                
                # Process steps
                for step_data in element.get('steps', []):
                    total_steps += 1
                    result = step_data.get('result', {})
                    step_status = result.get('status', 'undefined')
                    step_duration = result.get('duration', 0)
                    scenario_duration += step_duration
                    
                    step = {
                        'keyword': step_data.get('keyword', ''),
                        'name': step_data.get('name', ''),
                        'status': step_status,
                        'duration': step_duration,
                        'location': step_data.get('location', ''),
                        'error_message': result.get('error_message', ''),
                        'table': step_data.get('table', None)
                    }
                    
                    scenario['steps'].append(step)
                    
                    # Count step statuses
                    if step_status == 'passed':
                        passed_steps += 1
                    elif step_status == 'failed':
                        failed_steps += 1
                    elif step_status == 'skipped':
                        skipped_steps += 1
                    elif step_status == 'undefined':
                        undefined_steps += 1
                
                scenario['duration'] = scenario_duration
                scenario_durations.append(scenario_duration)
                total_duration += scenario_duration
                
                # Determine scenario status
                if any(s['status'] == 'failed' for s in scenario['steps']):
                    scenario['status'] = 'failed'
                    failed_scenarios += 1
                    feature['failed_count'] += 1
                    feature['status'] = 'failed'
                elif any(s['status'] == 'undefined' for s in scenario['steps']):
                    scenario['status'] = 'error'
                    error_scenarios += 1
                    feature['error_count'] += 1
                    if feature['status'] != 'failed':
                        feature['status'] = 'error'
                elif all(s['status'] == 'passed' for s in scenario['steps']):
                    scenario['status'] = 'passed'
                    passed_scenarios += 1
                    feature['passed_count'] += 1
                else:
                    scenario['status'] = 'skipped'
                    skipped_scenarios += 1
                
                feature['scenarios'].append(scenario)
            
            features.append(feature)
        
        # Calculate summary statistics
        self.report_data = {
            'metadata': {
                'title': self.title,
                'subtitle': 'Behavior-Driven Development Test Results',
                'icon': '📝',
                'generated_at': datetime.now().strftime('%B %d, %Y %H:%M:%S'),
                'timestamp': datetime.now().isoformat(),
            },
            'summary': {
                'total_features': len(features),
                'total_scenarios': total_scenarios,
                'passed_scenarios': passed_scenarios,
                'failed_scenarios': failed_scenarios,
                'error_scenarios': error_scenarios,
                'skipped_scenarios': skipped_scenarios,
                'pass_rate': round((passed_scenarios / total_scenarios * 100) if total_scenarios > 0 else 0, 1),
                'total_steps': total_steps,
                'passed_steps': passed_steps,
                'failed_steps': failed_steps,
                'skipped_steps': skipped_steps,
                'undefined_steps': undefined_steps,
                'total_duration': total_duration,
                'average_scenario_duration': sum(scenario_durations) / len(scenario_durations) if scenario_durations else 0,
                'fastest_scenario': min(scenario_durations) if scenario_durations else 0,
                'slowest_scenario': max(scenario_durations) if scenario_durations else 0
            },
            'features': features,
            'navigation_tabs': [
                ('overview', '📊 Overview'),
                ('features', '📋 Features'),
                ('requirements', '📑 Requirements')
            ]
        }
        
        print(f"✅ Parsed {len(features)} features, {total_scenarios} scenarios, {total_steps} steps")
        return True
    
    def _generate_content_sections(self) -> str:
        """Generate BDD-specific content sections"""
        return (
            self._generate_overview_section() +
            self._generate_features_section() +
            self._generate_requirements_section()
        )
    
    def _generate_overview_section(self) -> str:
        """Generate overview section with charts"""
        s = self.report_data['summary']
        
        # Summary cards
        cards_data = [
            {'type': 'total', 'icon': '📊', 'value': s['total_scenarios'], 'label': 'Total Scenarios'},
            {'type': 'passed', 'icon': '✅', 'value': s['passed_scenarios'], 'label': 'Passed'},
            {'type': 'failed', 'icon': '❌', 'value': s['failed_scenarios'], 'label': 'Failed'},
            {'type': 'error', 'icon': '⚠️', 'value': s['error_scenarios'], 'label': 'Error/Undefined'}
        ]
        
        # Pie chart data
        pie_data = {
            'Passed': s['passed_scenarios'],
            'Failed': s['failed_scenarios'],
            'Error': s['error_scenarios'],
            'Skipped': s['skipped_scenarios']
        }
        
        # Bar chart data
        features_data = []
        for f in self.report_data['features']:
            name = f['name'][:20] + '...' if len(f['name']) > 20 else f['name']
            features_data.append({
                'name': name,
                'passed': f['passed_count'],
                'failed': f['failed_count'],
                'error': f['error_count']
            })
        
        labels = [f['name'] for f in features_data]
        datasets = [
            {
                'label': 'Passed',
                'data': [f['passed'] for f in features_data],
                'backgroundColor': 'rgb(16, 185, 129)'
            },
            {
                'label': 'Failed',
                'data': [f['failed'] for f in features_data],
                'backgroundColor': 'rgb(239, 68, 68)'
            },
            {
                'label': 'Error',
                'data': [f['error'] for f in features_data],
                'backgroundColor': 'rgb(245, 158, 11)'
            }
        ]
        
        return f'''
<section id="overview" class="overview-section">
    <div class="container">
        <h2>📊 Test Results Overview</h2>
        
        {self._generate_summary_cards(cards_data)}
        
        <div class="charts-grid">
            {self._generate_pie_chart('statusPieChart', 'Status Distribution', pie_data)}
            {self._generate_bar_chart('featuresBarChart', 'Features Comparison', labels, datasets)}
        </div>
        
        <div class="stats-table">
            <h3>Detailed Statistics</h3>
            <table>
                <tr><th>Metric</th><th>Value</th></tr>
                <tr><td>Total Features</td><td>{s['total_features']}</td></tr>
                <tr><td>Total Scenarios</td><td>{s['total_scenarios']}</td></tr>
                <tr><td>Total Steps</td><td>{s['total_steps']}</td></tr>
                <tr><td>Pass Rate</td><td><strong>{s['pass_rate']}%</strong></td></tr>
                <tr><td>Execution Time</td><td>{self._format_duration(s['total_duration'])}</td></tr>
                <tr><td>Average Scenario Time</td><td>{self._format_duration(s['average_scenario_duration'])}</td></tr>
                <tr><td>Fastest Scenario</td><td>{self._format_duration(s['fastest_scenario'])}</td></tr>
                <tr><td>Slowest Scenario</td><td>{self._format_duration(s['slowest_scenario'])}</td></tr>
            </table>
        </div>
    </div>
</section>'''
    
    def _generate_features_section(self) -> str:
        """Generate features section with expandable scenarios"""
        html = '''
<section id="features" class="features-section" style="display:none;">
    <div class="container">
        <h2>📋 Features & Scenarios</h2>
        
        <div class="controls">
            <input type="text" id="searchBox" placeholder="🔍 Search scenarios..." onkeyup="filterItems('searchBox', '.item-card')">
            <select id="statusFilter" onchange="filterByStatus('statusFilter', '.item-card')">
                <option value="all">All Status</option>
                <option value="passed">✅ Passed Only</option>
                <option value="failed">❌ Failed Only</option>
                <option value="error">⚠️ Error Only</option>
            </select>
            <button onclick="expandAll()">Expand All</button>
            <button onclick="collapseAll()">Collapse All</button>
            <button onclick="expandAllFailed()">Expand Failed</button>
        </div>
        
        <div class="features-list">
'''
        
        for feature in self.report_data['features']:
            html += self._generate_feature_card(feature)
        
        html += '''
        </div>
    </div>
</section>'''
        
        return html
    
    def _generate_feature_card(self, feature: Dict) -> str:
        """Generate single feature card"""
        scenarios_html = ''
        for scenario in feature['scenarios']:
            scenarios_html += self._generate_scenario_card(scenario)
        
        pass_rate = round((feature['passed_count'] / len(feature['scenarios']) * 100) if feature['scenarios'] else 0, 1)
        tags_html = ''.join(f'<span class="tag">{tag}</span>' for tag in feature['tags'])
        
        return f'''
<div class="item-card {feature['status']}" id="{feature['id']}">
    <div class="item-header" onclick="toggleItem('{feature['id']}')">
        <div class="item-title">
            <span class="expand-icon">▶</span>
            <div>
                <h3>{feature['name']}</h3>
                <div class="tags">{tags_html}</div>
            </div>
        </div>
        <div class="item-stats">
            <span class="count">{len(feature['scenarios'])} scenarios</span>
            <span class="pass-rate">{pass_rate}%</span>
            <span class="status-indicator {feature['status']}">●</span>
        </div>
    </div>
    <div class="item-body" id="{feature['id']}-body">
        {f'<div class="description">{feature["description"]}</div>' if feature['description'] else ''}
        <div class="scenarios-list">
            {scenarios_html}
        </div>
    </div>
</div>'''
    
    def _generate_scenario_card(self, scenario: Dict) -> str:
        """Generate single scenario card"""
        steps_html = ''
        for step in scenario['steps']:
            steps_html += self._generate_step_item(step)
        
        tags_html = ''.join(f'<span class="tag">{tag}</span>' for tag in scenario['tags'])
        
        return f'''
<div class="item-card {scenario['status']}" style="margin-left: 20px; margin-bottom: 16px;">
    <div class="item-header" onclick="toggleItem('{scenario['id']}')">
        <div class="item-title">
            <span class="expand-icon">▶</span>
            <h4>{scenario['name']}</h4>
        </div>
        <div class="item-stats">
            <span class="duration">⏱️ {self._format_duration(scenario['duration'])}</span>
            <span class="status-badge {scenario['status']}">{scenario['status']}</span>
        </div>
    </div>
    <div class="item-body" id="{scenario['id']}-body">
        <div class="tags" style="margin-bottom: 16px;">{tags_html}</div>
        <ol style="list-style: none; counter-reset: step-counter; padding-left: 24px;">
            {steps_html}
        </ol>
    </div>
</div>'''
    
    def _generate_step_item(self, step: Dict) -> str:
        """Generate single step item"""
        status_icon = self._get_status_icon(step['status'])
        
        # Step styles based on status
        step_class = step['status']
        
        step_html = f'''
<li class="item-card {step_class}" style="margin-bottom: 8px; padding: 12px; position: relative; counter-increment: step-counter;">
    <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
        <span style="font-weight: 700; font-size: 16px;">{status_icon}</span>
        <span style="font-weight: 700; color: var(--primary); min-width: 60px;">{step['keyword']}</span>
        <span style="flex: 1;">{step['name']}</span>
        <span class="duration" style="background: white; padding: 2px 8px; border-radius: 4px;">{self._format_duration(step['duration'])}</span>
    </div>
    {f'<div style="font-size: 11px; color: var(--text-gray); margin-top: 4px;">{step["location"]}</div>' if step['location'] else ''}
'''
        
        # Add error details if failed
        if step['status'] == 'failed' and step.get('error_message'):
            step_html += f'''
    <div class="error-details">
        <div class="error-header">❌ Error Message</div>
        <pre class="error-message">{step['error_message']}</pre>
    </div>'''
        
        # Add data table if present
        if step.get('table'):
            step_html += self._generate_step_table(step['table'])
        
        step_html += '</li>'
        return step_html
    
    def _generate_step_table(self, table: Any) -> str:
        """Generate data table for step"""
        if not table:
            return ''
        
        # Handle different table formats
        if isinstance(table, dict):
            rows = table.get('rows', [])
        elif isinstance(table, list):
            rows = table
        else:
            return ''
        
        if not rows:
            return ''
        
        html = '<table style="margin-top: 8px; width: 100%; border-collapse: collapse;">'
        
        # First row is typically headers
        if rows:
            html += '<tr>'
            first_row = rows[0]
            if isinstance(first_row, dict):
                headers = first_row.get('cells', first_row.get('values', []))
            elif isinstance(first_row, list):
                headers = first_row
            else:
                headers = []
            
            for header in headers:
                html += f'<th style="padding: 8px; border: 1px solid var(--border); background: var(--bg-light); font-weight: 600;">{header}</th>'
            html += '</tr>'
            
            # Data rows
            for row in rows[1:]:
                html += '<tr>'
                if isinstance(row, dict):
                    cells = row.get('cells', row.get('values', []))
                elif isinstance(row, list):
                    cells = row
                else:
                    cells = []
                
                for cell in cells:
                    html += f'<td style="padding: 8px; border: 1px solid var(--border);">{cell}</td>'
                html += '</tr>'
        
        html += '</table>'
        return html
    
    def _generate_requirements_section(self) -> str:
        """Generate requirements/tags grouping section"""
        # Group scenarios by tags
        tags_map = {}
        for feature in self.report_data['features']:
            for scenario in feature['scenarios']:
                for tag in scenario['tags']:
                    if tag not in tags_map:
                        tags_map[tag] = []
                    tags_map[tag].append({
                        'name': scenario['name'],
                        'status': scenario['status'],
                        'id': scenario['id']
                    })
        
        html = '''
<section id="requirements" class="requirements-section" style="display:none;">
    <div class="container">
        <h2>📑 Requirements & Tags Coverage</h2>
        <div style="background: white; padding: 24px; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
'''
        
        for tag, scenarios in sorted(tags_map.items()):
            passed = sum(1 for s in scenarios if s['status'] == 'passed')
            total = len(scenarios)
            coverage = (passed / total * 100) if total > 0 else 0
            
            html += f'''
        <div style="margin-bottom: 24px;">
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px; background: var(--bg-light); border-radius: 6px; margin-bottom: 12px;">
                <h3>{tag}</h3>
                <div style="display: flex; align-items: center; gap: 12px;">
                    <span>{passed}/{total} scenarios</span>
                    <div style="height: 8px; background: #e5e7eb; border-radius: 4px; overflow: hidden; width: 200px;">
                        <div style="height: 100%; background: linear-gradient(90deg, var(--success) 0%, #059669 100%); width: {coverage}%;"></div>
                    </div>
                </div>
            </div>
            <ul style="list-style: none; padding-left: 24px;">
'''
            
            for scenario in scenarios:
                status_icon = self._get_status_icon(scenario['status'])
                html += f'<li style="padding: 8px 0; border-bottom: 1px solid var(--border);">{status_icon} <a href="#{scenario["id"]}" style="color: var(--primary); text-decoration: none;">{scenario["name"]}</a></li>'
            
            html += '''
            </ul>
        </div>'''
        
        html += '''
        </div>
    </div>
</section>'''
        
        return html


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description='Generate enhanced BDD HTML report')
    parser.add_argument('--input', required=True, help='Input behave JSON file')
    parser.add_argument('--output', required=True, help='Output HTML file path')
    parser.add_argument('--title', default='BDD Test Report', help='Report title')
    
    args = parser.parse_args()
    
    generator = BDDReportGenerator(
        behave_json_path=args.input,
        output_html_path=args.output,
        title=args.title
    )
    
    success = generator.generate_report()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

