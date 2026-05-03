#!/usr/bin/env python3
"""
Generate Integration Test Report
CLI script to generate enhanced HTML reports from integration test JSON output
"""

import sys
import os
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from integration_report_generator import IntegrationTestReportGenerator


def main():
    parser = argparse.ArgumentParser(
        description='Generate enhanced integration test HTML report from pytest JSON output',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Basic usage
  %(prog)s --input test_results.json --output report.html
  
  # With custom title
  %(prog)s --input results.json --output report.html --title "API Integration Tests"
  
  # Typical workflow
  pytest tests/integration/python -v --json-report --json-report-file=results.json
  %(prog)s --input results.json --output integration_report.html
'''
    )
    
    parser.add_argument('--input', '-i', required=True,
                       help='Input pytest JSON results file')
    parser.add_argument('--output', '-o', required=True,
                       help='Output HTML report file')
    parser.add_argument('--title', '-t', default='Integration Test Report',
                       help='Report title (default: Integration Test Report)')
    
    args = parser.parse_args()
    
    # Validate input file exists
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Error: Input file not found: {args.input}")
        return 1
    
    # Create output directory if needed
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("  Integration Test Report Generator")
    print("=" * 60)
    print()
    print(f"📥 Input:  {args.input}")
    print(f"📤 Output: {args.output}")
    print(f"📝 Title:  {args.title}")
    print()
    
    # Generate report
    generator = IntegrationTestReportGenerator(args.input, args.output, args.title)
    
    success = generator.generate_report()
    
    if success:
        print()
        print("=" * 60)
        print("  ✅ Integration Test Report Generated Successfully!")
        print("=" * 60)
        print()
        print(f"📊 View report: file://{output_path.absolute()}")
        print()
        return 0
    else:
        print()
        print("=" * 60)
        print("  ❌ Report Generation Failed")
        print("=" * 60)
        return 1


if __name__ == '__main__':
    sys.exit(main())

