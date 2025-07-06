## generate_data_orchestrator.py

Salesforce CLI と連携し、指定オブジェクトの定義取得からテストデータ生成、Bulk API インポート、結果取得までを自動化する Python スクリプトです。

---

### 概要

1. **SObject 定義の取得** (`sf sobject describe`)
2. **テストデータ生成** (`generate_test_data.py` 呼び出し)
3. **Bulk API インポート** (`sf data import bulk`)
4. **インポート結果取得** (`sf data bulk results`)

異常終了時には CLI の返す JSON 内 `actions` に記載されたコマンドを自動で実行し、`results/bulk_result` 配下に出力します。

---

### ディレクトリ構成

```
project_root/
├─ scripts/
│   ├─ generate_test_data.py
│   └─ generate_data_orchestrator.py   ← 本スクリプト
└─ results/
    ├─ description/   ← <Object>.json (describe 結果)
    ├─ data/          ← <Object>.csv (テストデータ)
    └─ bulk_result/   ← Bulk API 結果ファイル
```

---

### 使い方

```bash
git clone <repo>
cd project_root
python scripts/generate_data_orchestrator.py \
  --object Account \
  --rows 100 \
  --describe results/description/Account.json \
  --out results/data/Account.csv \
  [--skip-fields Field1,Field2] \
  [--person-rt-dev-name <DevName>] \
  [--org myOrgAlias] \
  [--line-ending LF|CRLF] \
  [--wait <minutes>] \
  [--skip-import]
```

- `--object`: SObject API 名
- `--rows`: 生成する行数
- `--skip-fields`: テストデータ作成をスキップするフィールド名のカンマ区切り
- `--person-rt-dev-name`: Account の個人取引先用 Record Type DeveloperName
- `--org`: Salesforce org エイリアス (`-u` 相当)
- `--line-ending`: CSV の改行コード（デフォルト `CRLF`）
- `--wait`: Bulk API 完了待機時間（分、デフォルト `10`）
- `--skip-import`: CSV 生成後に Bulk API インポートをスキップし、CSV 生成のみを行う

---

### 処理フロー解説

1. **Describe 実行**

   - `sf sobject describe --sobject <Object> --json`
   - 戻り JSON を `results/description/<Object>.json` に保存

2. **テストデータ生成**

   - `python generate_test_data.py --describe ... --rows ... --out ...`
   - フィールド定義をもとに `string`/`textarea` は可変長日本語、picklist/multipicklist、数値、電話、email、URL、日付、datetime、緯度/経度、住所 compound、個人取引先/法人取引先切替など多様な型対応を実施

3. **Bulk API インポート**

   - `sf data import bulk --sobject <Object> --file <CSV> --line-ending <> --wait <> --json [-o <org>]`
   - 成功時は JobId を取得し次工程へ

4. **失敗時のフォールバック**

   - CLI の JSON から `"actions"` 要素を抽出し、推奨コマンドを自動実行

5. **結果取得**

   - `sf data bulk results --job-id <JobId> [-o <org>]`
   - `results/bulk_result/` 配下に失敗レコードなどをダウンロード

---

### 依存ライブラリ

- Python 標準ライブラリのみ
- Salesforce CLI (`sf` コマンド) が前提

---

### 備考

- 実行はプロジェクトルートから行う想定です。
- エラー発生時は標準エラー出力にも詳細を出力します。

---

詳しい動作やオプションの組み合わせはソースコード中のヘッダーコメントも参照してください。
