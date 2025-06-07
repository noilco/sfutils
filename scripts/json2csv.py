#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import csv
import sys
from pathlib import Path

def json_fields_to_csv(json_path, csv_path=None):
    """
    指定 JSON ファイルの "fields" 配列を読み込み、
    CSV に出力します。
    列順は以下の優先リストに従い、
    それ以外のキーは JSON に出現した順序を保持します。

    優先リスト:
      label, name, nillable, length, precision, scale, picklistValues
    """
    # JSON 読み込み
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)

    fields = data.get("fields")
    if fields is None:
        print(f"Error: JSON に 'fields' キーが見つかりません: {json_path}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(fields, list):
        print(f"Error: 'fields' の値が配列ではありません: {type(fields)}", file=sys.stderr)
        sys.exit(1)

    # JSON 内でのキー出現順を収集
    ordered_keys = []
    for fld in fields:
        for key in fld.keys():
            if key not in ordered_keys:
                ordered_keys.append(key)

    # 優先的に先頭に置くキー
    priority = ["label", "name", "nillable", "length", "precision", "scale", "picklistValues"]
    # 実際に出力する列順を構築
    fieldnames = []
    for key in priority:
        if key in ordered_keys:
            fieldnames.append(key)
    for key in ordered_keys:
        if key not in fieldnames:
            fieldnames.append(key)

    # 出力先ハンドルを決定
    if csv_path:
        out_file = open(csv_path, "w", newline="", encoding="utf-8")
    else:
        out_file = sys.stdout

    writer = csv.DictWriter(out_file, fieldnames=fieldnames)
    writer.writeheader()

    for fld in fields:
        # ネスト構造は JSON 文字列化
        row = {}
        for key in fieldnames:
            val = fld.get(key, "")
            if isinstance(val, (list, dict)):
                val = json.dumps(val, ensure_ascii=False)
            row[key] = val
        writer.writerow(row)

    if csv_path:
        out_file.close()

def main():
    prog = Path(sys.argv[0]).name
    if len(sys.argv) < 2:
        print(f"Usage: {prog} <input.json> [output.csv]", file=sys.stderr)
        sys.exit(1)

    json_path = sys.argv[1]
    csv_path = sys.argv[2] if len(sys.argv) >= 3 else None
    json_fields_to_csv(json_path, csv_path)

if __name__ == "__main__":
    main()
