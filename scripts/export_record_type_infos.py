#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Extract the `recordTypeInfos` array from a JSON file (e.g. output of
`sf sobject describe --json`) and write it out as CSV.

Usage:
    python export_record_types.py input.json [output.csv]
"""

import json
import csv
import sys
from pathlib import Path

def export_record_type_infos(json_path, csv_path=None):
    # Load the JSON
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)

    # Extract recordTypeInfos
    infos = data.get('recordTypeInfos', [])
    if not infos:
        print(f"No recordTypeInfos found in {json_path}", file=sys.stderr)
        sys.exit(1)

    # Determine CSV columns: top-level keys plus flatten 'urls'
    fieldnames = []
    for info in infos:
        for key in info:
            if key == 'urls' and isinstance(info['urls'], dict):
                # flatten each entry under urls as its own column
                for subkey in info['urls']:
                    if subkey not in fieldnames:
                        fieldnames.append(subkey)
            else:
                if key not in fieldnames:
                    fieldnames.append(key)

    # Write CSV
    out_f = open(csv_path, 'w', newline='', encoding='utf-8') if csv_path else sys.stdout
    writer = csv.DictWriter(out_f, fieldnames=fieldnames)
    writer.writeheader()

    # Populate rows
    for info in infos:
        row = {}
        for col in fieldnames:
            if col in info:
                row[col] = info[col]
            elif 'urls' in info and isinstance(info['urls'], dict) and col in info['urls']:
                row[col] = info['urls'][col]
            else:
                row[col] = ''
        writer.writerow(row)

    if csv_path:
        out_f.close()
        print(f"Wrote {len(infos)} record types to {csv_path}", file=sys.stderr)

def main():
    prog = Path(sys.argv[0]).stem
    if len(sys.argv) not in (2, 3):
        print(f"Usage: {prog} <input.json> [output.csv]", file=sys.stderr)
        sys.exit(1)

    in_json = sys.argv[1]
    out_csv = sys.argv[2] if len(sys.argv) == 3 else None
    export_record_type_infos(in_json, out_csv)

if __name__ == '__main__':
    main()
