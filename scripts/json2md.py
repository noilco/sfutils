#!/usr/bin/env python3
import json
import sys

def to_markdown(obj, indent_level=0):
    md = ''
    indent = '  ' * indent_level

    if isinstance(obj, dict):
        for key, value in obj.items():
            # ネストするオブジェクトや配列は見出しを付けて再帰処理
            if isinstance(value, (dict, list)):
                md += f"{indent}## {key}\n\n"
                md += to_markdown(value, indent_level + 1)
            else:
                md += f"{indent}- **{key}**: {value}\n"
        md += "\n"

    elif isinstance(obj, list):
        if not obj:
            return md
        # リスト内の要素が全て dict ならテーブルに
        if all(isinstance(item, dict) for item in obj):
            # 全てのキーを列ヘッダとして収集
            headers = sorted({k for item in obj for k in item.keys()})
            # ヘッダー行
            md += indent + "| " + " | ".join(headers) + " |\n"
            md += indent + "| " + " | ".join("----" for _ in headers) + " |\n"
            # 各行
            for item in obj:
                row = [str(item.get(h, "")) for h in headers]
                md += indent + "| " + " | ".join(row) + " |\n"
            md += "\n"
        else:
            # プリミティブやネスト構造は箇条書きで
            for item in obj:
                if isinstance(item, (dict, list)):
                    md += f"{indent}-\n" + to_markdown(item, indent_level + 1)
                else:
                    md += f"{indent}- {item}\n"
            md += "\n"

    else:
        # それ以外はプレーンテキスト
        md += indent + str(obj) + "\n"

    return md

def main():
    if len(sys.argv) < 2:
        print("Usage: python json2md.py path/to/file.json")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    markdown = to_markdown(data)
    print(markdown)

if __name__ == '__main__':
    main()
