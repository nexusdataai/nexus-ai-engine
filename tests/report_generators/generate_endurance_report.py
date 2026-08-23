#!/usr/bin/env python3
"""
Generate Endurance Test Report - Standalone CLI Tool
Usage: python generate_endurance_report.py --input results.json --output report.html
"""

import sys
import argparse
from pathlib import Path

# Handle imports
try:
    from endurance_report_generator import EnduranceReportGenerator
except ImportError:
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from endurance_report_generator import EnduranceReportGenerator


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Generate enhanced Endurance HTML report from JSON output',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Basic usage
  python generate_endurance_report.py --input endurance_report.json --output report.html
  
  # Custom title
  python generate_endurance_report.py --input results.json --output report.html --title "Endurance Test"
  
  # From test runner
  python tests/report_generators/generate_endurance_report.py \\
    --input tests/reports/endurance/endurance_report.json \\
    --output tests/reports/endurance/endurance_report_enhanced.html
        '''
    )
    
    parser.add_argument('--input', '-i',
                        required=True,
                        help='Input endurance JSON file')
    parser.add_argument('--output', '-o',
                        required=True,
                        help='Output HTML file path')
    parser.add_argument('--title', '-t',
                        default='Endurance Test Report',
                        help='Report title (default: Endurance Test Report)')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("  Endurance Test Report Generator")
    print("=" * 60)
    print()
    print(f"📥 Input:  {args.input}")
    print(f"📤 Output: {args.output}")
    print(f"📝 Title:  {args.title}")
    print()
    
    # Check if input file exists
    if not Path(args.input).exists():
        print(f"❌ Error: Input file not found: {args.input}")
        sys.exit(1)
    
    generator = EnduranceReportGenerator(
        json_path=args.input,
        output_html_path=args.output,
        title=args.title
    )
    
    success = generator.generate_report()
    
    if success:
        print()
        print("=" * 60)
        print("  ✅ Endurance Test Report Generated Successfully!")
        print("=" * 60)
        print()
        print(f"📊 View report: file://{Path(args.output).absolute()}")
        sys.exit(0)
    else:
        print()
        print("=" * 60)
        print("  ❌ Failed to Generate Report")
        print("=" * 60)
        sys.exit(1)


if __name__ == '__main__':
    main()

