#!/usr/bin/env python3
"""
Generate BDD Test Report - Standalone CLI Tool
Usage: python generate_bdd_report.py --input results.json --output report.html
"""

import sys
import argparse
from bdd_report_generator import BDDReportGenerator


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Generate enhanced BDD HTML report from behave JSON output',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Basic usage
  python generate_bdd_report.py --input behave-results.json --output report.html
  
  # Custom title
  python generate_bdd_report.py --input results.json --output report.html --title "My BDD Tests"
  
  # From test runner
  python tests/report_generators/generate_bdd_report.py \\
    --input test_reports/bdd/results.json \\
    --output test_reports/bdd/index.html
        '''
    )
    
    parser.add_argument('--input', '-i',
                        required=True,
                        help='Input behave JSON file (behave --format json)')
    parser.add_argument('--output', '-o',
                        required=True,
                        help='Output HTML file path')
    parser.add_argument('--title', '-t',
                        default='BDD Test Report',
                        help='Report title (default: BDD Test Report)')
    
    args = parser.parse_args()
    
    print(f"📝 Generating BDD report...")
    print(f"   Input:  {args.input}")
    print(f"   Output: {args.output}")
    print(f"   Title:  {args.title}")
    print()
    
    generator = BDDReportGenerator(
        behave_json_path=args.input,
        output_html_path=args.output,
        title=args.title
    )
    
    success = generator.generate_report()
    
    if success:
        print(f"\n✅ Successfully generated BDD report: {args.output}")
        sys.exit(0)
    else:
        print(f"\n❌ Failed to generate BDD report")
        sys.exit(1)


if __name__ == '__main__':
    main()

