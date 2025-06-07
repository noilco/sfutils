#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_test_data.py

Salesforce “describe” JSON からテストデータ CSV を生成します。

- 複数の RecordType がある場合、
  名前が「マスター」または「マスタ」のものは除外します。
"""

import json
import csv
import random
import argparse
import sys

# JIS 第1・第2水準に相当する日本語文字プール
HIRAGANA = [chr(i) for i in range(0x3041, 0x3097)]
KATAKANA = [chr(i) for i in range(0x30A1, 0x30FB)]
KANJI    = [chr(i) for i in range(0x4E00, 0x9FFF)]
# ひらがな45%, カタカナ45%, 漢字10%
POOL_WEIGHTS = [0.45, 0.45, 0.10]
POOLS = [HIRAGANA, KATAKANA, KANJI]

# システム／監査項目（ユーザーが直接設定しない）
SYSTEM_FIELDS = {
    "IsDeleted", "CreatedById", "CreatedDate",
    "LastModifiedById", "LastModifiedDate", "SystemModstamp"
}

# 数値型とみなす type の一覧
NUMERIC_TYPES = {"double", "currency", "percent", "int", "integer"}

# 除外するレコードタイプ名
EXCLUDE_RT_NAMES = {"マスター", "マスタ"}

def random_japanese(max_len):
    """ひらがな・カタカナ多めのランダム日本語文字列を返す"""
    length = random.randint(1, max(1, max_len))
    result = []
    for _ in range(length):
        pool = random.choices(POOLS, weights=POOL_WEIGHTS, k=1)[0]
        result.append(random.choice(pool))
    return ''.join(result)

def random_number(precision, scale):
    """precision: 全桁数, scale: 小数点以下桁数"""
    int_digits = max(1, precision - scale)
    max_int = 10**int_digits - 1
    integer = random.randint(0, max_int)
    if scale > 0:
        frac = ''.join(str(random.randint(0,9)) for _ in range(scale))
        return f"{integer}.{frac}"
    return str(integer)

def parse_args():
    p = argparse.ArgumentParser(description="Generate Salesforce test data CSV")
    p.add_argument("--describe", required=True,
                   help="sf sobject describe 出力 JSON ファイル")
    p.add_argument("--rows",    type=int, default=10,
                   help="生成する行数 (default=10)")
    p.add_argument("--skip-fields", default="",
                   help="値を空欄にするフィールド名をカンマ区切りで指定")
    p.add_argument("--out",     help="出力先 CSV パス (省略→stdout)")
    return p.parse_args()

def main():
    args = parse_args()

    skip_fields = {f.strip() for f in args.skip_fields.split(",") if f.strip()}

    # describe JSON 読み込み
    with open(args.describe, encoding="utf-8") as f:
        meta = json.load(f)

    # fields 定義を取り出し、calculated およびシステム項目を除外
    fields = [
        f for f in meta.get("fields", [])
        if not f.get("calculated", False)
        and f.get("name") not in SYSTEM_FIELDS
    ]

    # recordTypeInfos から、active かつ名前が「マスター」「マスタ」でない ID リストを抽出
    record_type_ids = [
        rt["recordTypeId"]
        for rt in meta.get("recordTypeInfos", [])
        if rt.get("active", False)
           and rt.get("name") not in EXCLUDE_RT_NAMES
    ]

    if not fields:
        print("Error: 有効な fields がありません。", file=sys.stderr)
        sys.exit(1)

    # CSV ヘッダーはフィールド名(name)の順
    headers = [fld["name"] for fld in fields]

    # 出力先設定
    out_f = open(args.out, "w", newline="", encoding="utf-8") if args.out else sys.stdout
    writer = csv.DictWriter(out_f, fieldnames=headers)
    writer.writeheader()

    for _ in range(args.rows):
        row = {}
        for fld in fields:
            name      = fld["name"]
            if name in skip_fields:
                row[name] = ""
                continue

            ftype     = fld.get("type", "").lower()
            length    = int(fld.get("length") or 0)
            precision = int(fld.get("precision") or 0)
            scale     = int(fld.get("scale") or 0)
            raw_vals  = fld.get("picklistValues", [])

            val = ""
            if name == "RecordTypeId":
                val = random.choice(record_type_ids) if record_type_ids else ""
            elif ftype in ("string", "textarea"):
                maxlen = length or 10
                val = random_japanese(maxlen)
            elif ftype == "picklist":
                choices = [o["value"] for o in raw_vals if "value" in o]
                val = random.choice(choices) if choices else ""
            elif ftype in ("multipicklist", "multiselectpicklist"):
                choices = [o["value"] for o in raw_vals if "value" in o]
                if choices:
                    cnt = random.randint(1, len(choices))
                    val = ";".join(random.sample(choices, cnt))
            elif ftype in NUMERIC_TYPES:
                if precision > 0:
                    val = random_number(precision, scale)
                else:
                    val = str(random.randint(0, 1000))
            # reference and others → 空欄

            row[name] = val

        writer.writerow(row)

    if args.out:
        out_f.close()
        print(f"Written: {args.out}", file=sys.stderr)

if __name__ == "__main__":
    main()
