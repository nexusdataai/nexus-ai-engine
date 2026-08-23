#!/usr/bin/env python3
"""
Generate Unit Test Report - Standalone CLI Tool
Usage: python generate_unit_report.py --input results.json --output report.html
"""

import sys
import argparse
from unit_report_generator import UnitTestReportGenerator


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Generate enhanced unit test HTML report from pytest JSON output',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Basic usage
  python generate_unit_report.py --input pytest-results.json --output report.html
  
  # Custom title
  python generate_unit_report.py --input results.json --output report.html --title "My Unit Tests"
  
  # From test runner
  python tests/report_generators/generate_unit_report.py \\
    --input tests/reports/unit/unit_test_results.json \\
    --output tests/reports/unit/unit_test_report_enhanced.html
        '''
    )
    
    parser.add_argument('--input', '-i',
                        required=True,
                        help='Input pytest JSON file (pytest --json-report)')
    parser.add_argument('--output', '-o',
                        required=True,
                        help='Output HTML file path')
    parser.add_argument('--title', '-t',
                        default='Unit Test Report',
                        help='Report title (default: Unit Test Report)')
    
    args = parser.parse_args()
    
    print(f"🧪 Generating unit test report...")
    print(f"   Input:  {args.input}")
    print(f"   Output: {args.output}")
    print(f"   Title:  {args.title}")
    print()
    
    generator = UnitTestReportGenerator(
        pytest_json_path=args.input,
        output_html_path=args.output,
        title=args.title
    )
    
    success = generator.generate_report()
    
    if success:
        print(f"\n✅ Successfully generated unit test report: {args.output}")
        sys.exit(0)
    else:
        print(f"\n❌ Failed to generate unit test report")
        sys.exit(1)


if __name__ == '__main__':
    main()

