#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import csv
import sys
from pathlib import Path

def main():
    if len(sys.argv) < 3:
        prog = Path(sys.argv[0]).name
        print(f"Usage: {prog} <Account.json> <CustomField.json> [output.csv]", file=sys.stderr)
        sys.exit(1)

    account_path = Path(sys.argv[1])
    custom_path  = Path(sys.argv[2])
    out_path     = Path(sys.argv[3]) if len(sys.argv) >= 4 else None

    # 1) JSON 読み込み
    account = json.loads(account_path.read_text(encoding='utf-8'))
    custom  = json.loads(custom_path.read_text(encoding='utf-8'))

    account_fields = account.get("fields", [])
    if not account_fields:
        print(f"Error: {account_path} に 'fields' セクションが見つかりません。", file=sys.stderr)
        sys.exit(1)

    # 2) name → 日本語ラベル マッピング
    label_map = {
        fld["name"]: fld.get("label", fld["name"])
        for fld in custom.get("fields", [])
    }  # :contentReference[oaicite:2]{index=2}

    # 3) CSV の列（フィールド）順は JSON 内の順序をそのまま利用
    field_names = [f["name"] for f in account_fields]

    # 4) 全フィールド定義で共通のプロパティ名を集める
    prop_keys = []
    for fld in account_fields:
        for k in fld.keys():
            if k not in prop_keys:
                prop_keys.append(k)

    # 5) CSV 書き出し
    writer = csv.writer(out_path.open('w', encoding='utf-8', newline='') if out_path else sys.stdout)

    # ヘッダー行：先頭は「プロパティ名」、以降は各フィールドの日本語ラベル
    header = ["Property"] + [ label_map.get(n, n) for n in field_names ]
    writer.writerow(header)

    # 各プロパティごとに 1 行ずつ書く
    for prop in prop_keys:
        row = [prop]
        for fld in account_fields:
            # 値が None の場合は空文字
            val = fld.get(prop, "")
            # リストや dict は JSON 文字列化
            if isinstance(val, (list, dict)):
                val = json.dumps(val, ensure_ascii=False)
            row.append(val)
        writer.writerow(row)

    if out_path:
        print(f"Written: {out_path}")

if __name__ == "__main__":
    main()
