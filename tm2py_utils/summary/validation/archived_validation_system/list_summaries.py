#!/usr/bin/env python3
"""
List configured summaries and their types

This utility script shows all summaries configured in validation_config.yaml,
organized by summary type (core vs validation).

Usage:
    python list_summaries.py
    python list_summaries.py --config path/to/validation_config.yaml
"""

import argparse
import yaml
from pathlib import Path
from collections import defaultdict


def load_config(config_path: Path) -> dict:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def list_summaries(config_path: Path):
    """List all summaries organized by type."""
    config = load_config(config_path)
    
    custom_summaries = config.get('custom_summaries', [])
    generate_setting = config.get('generate_summaries', 'all')
    
    # Organize by type
    by_type = defaultdict(list)
    by_data_source = defaultdict(list)
    
    for summary in custom_summaries:
        summary_type = summary.get('summary_type', 'core')
        data_source = summary.get('data_source', 'unknown')
        by_type[summary_type].append(summary)
        by_data_source[data_source].append(summary)
    
    # Print summary
    print("=" * 80)
    print("CONFIGURED SUMMARIES")
    print("=" * 80)
    print(f"Config file: {config_path}")
    print(f"Generate setting: {generate_setting}")
    print(f"Total summaries: {len(custom_summaries)}")
    print()
    
    # By summary type
    print("BY SUMMARY TYPE:")
    print("-" * 80)
    for summary_type in ['core', 'validation']:
        summaries = by_type[summary_type]
        print(f"\n{summary_type.upper()} ({len(summaries)} summaries):")
        if generate_setting == 'all' or generate_setting == summary_type:
            print("  ✓ WILL BE GENERATED")
        else:
            print("  ✗ FILTERED OUT (not matching generate_summaries setting)")
        
        for summary in summaries:
            name = summary.get('name', 'unnamed')
            desc = summary.get('description', '')
            source = summary.get('data_source', 'unknown')
            print(f"  • {name:40s} [{source}]")
            if desc:
                print(f"    {desc}")
    
    # By data source
    print("\n" + "=" * 80)
    print("BY DATA SOURCE:")
    print("-" * 80)
    for data_source, summaries in sorted(by_data_source.items()):
        print(f"\n{data_source.upper()} ({len(summaries)} summaries):")
        for summary in summaries:
            name = summary.get('name', 'unnamed')
            summary_type = summary.get('summary_type', 'core')
            print(f"  • {name:40s} [{summary_type}]")
    
    print("\n" + "=" * 80)
    print("SUMMARY:")
    print("-" * 80)
    print(f"Core summaries:       {len(by_type['core'])}")
    print(f"Validation summaries: {len(by_type['validation'])}")
    print(f"Total:                {len(custom_summaries)}")
    print()
    print(f"Current setting: generate_summaries = '{generate_setting}'")
    if generate_setting == 'core':
        print(f"  → Will generate {len(by_type['core'])} core summaries only")
    elif generate_setting == 'validation':
        print(f"  → Will generate {len(by_type['validation'])} validation summaries only")
    else:
        print(f"  → Will generate all {len(custom_summaries)} summaries")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="List configured summaries and their types",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--config',
        type=Path,
        default=Path(__file__).parent / 'validation_config.yaml',
        help='Path to validation configuration file (default: validation_config.yaml in same directory)'
    )
    
    args = parser.parse_args()
    
    if not args.config.exists():
        print(f"Error: Configuration file not found: {args.config}")
        return 1
    
    list_summaries(args.config)
    return 0


if __name__ == '__main__':
    exit(main())
