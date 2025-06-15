#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_data_orchestrator.py

指定オブジェクトの定義を Salesforce CLI で取得し、
同scriptsフォルダ内の generate_test_data.py を呼び出してテストデータCSVを作成します。
その後 Bulk API でインポートし、失敗時には提案されたコマンドを実行して結果を bulk_result フォルダに保存します。

出力フォルダ構成:
 project_root/
 ├─ scripts/
 │   ├─ generate_test_data.py
 │   └─ generate_data_orchestrator.py
 └─ results/
     ├─ description/   ← <Object>.json (describe)
     ├─ data/          ← <Object>.csv (テストデータ)
     └─ bulk_result/   ← Bulk API resultファイル

Usage (project root で実行):
    python scripts/generate_data_orchestrator.py \
        --object Account \
        --rows 100 \
        [--skip-fields Field1,Field2] \
        [--org myOrgAlias] \
        [--line-ending LF|CRLF] \
        [--wait <minutes>]
"""
import subprocess
import argparse
import sys
import os
import json
import re
import shlex

# スクリプト配置ディレクトリ
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# generate_test_data.py のパス
SCRIPT_PATH = os.path.join(SCRIPT_DIR, 'generate_test_data.py')
# プロジェクトルート
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))
# results 配下ディレクトリ
RESULTS_DIR = os.path.join(PROJECT_ROOT, 'results')


def init_output_dirs():
    desc = os.path.join(RESULTS_DIR, 'description')
    data = os.path.join(RESULTS_DIR, 'data')
    bulk = os.path.join(RESULTS_DIR, 'bulk_result')
    os.makedirs(desc, exist_ok=True)
    os.makedirs(data, exist_ok=True)
    os.makedirs(bulk, exist_ok=True)
    return desc, data, bulk


def run_cmd(cmd, capture_output=False, cwd=None):
    res = subprocess.run(cmd,
                         cwd=cwd or PROJECT_ROOT,
                         stdout=subprocess.PIPE if capture_output else None,
                         stderr=subprocess.PIPE,
                         text=True)
    return res


def main():
    p = argparse.ArgumentParser(
        description='Describe, generate, and bulk import with fallback')
    p.add_argument('--object', required=True)
    p.add_argument('--rows', type=int, required=True)
    p.add_argument('--skip-fields', default='')
    p.add_argument('--org', default=None)
    p.add_argument('--line-ending', choices=['LF','CRLF'], default='CRLF')
    p.add_argument('--wait', type=int, default=10)
    p.add_argument('--person-rt-dev-name', default='')
    args = p.parse_args()

    obj = args.object
    desc_dir, data_dir, bulk_dir = init_output_dirs()

    # 1) describe
    desc_path = os.path.join(desc_dir, f"{obj}.json")
    cmd = ['sf','sobject','describe','--sobject',obj]
    if args.org: cmd += ['-u', args.org]
    r = run_cmd(cmd, capture_output=True)
    if r.returncode != 0:
        sys.stderr.write(f"ERROR describe:\n{r.stderr}\n")
        sys.exit(1)
    with open(desc_path,'w',encoding='utf-8') as f:
        f.write(r.stdout)
    print(f"Describe saved: {desc_path}")

    # 2) generate
    data_path = os.path.join(data_dir, f"{obj}.csv")
    gen = [sys.executable, SCRIPT_PATH,
           '--describe', desc_path,
           '--rows', str(args.rows),
           '--out', data_path]
    if args.skip_fields:
        gen += ['--skip-fields', args.skip_fields]
    if args.person_rt_dev_name:
        gen += ['--person-rt-dev-name', args.person_rt_dev_name]
    g = run_cmd(gen, capture_output=True)
    if g.returncode != 0:
        sys.stderr.write(f"ERROR generate:\n{g.stderr}\n")
        sys.exit(1)
    print(f"Test data saved: {data_path}")

    # 3) bulk import
    imp = ['sf','data','import','bulk',
           '--sobject', obj,
           '--file', data_path,
           '--line-ending', args.line_ending,
           '--wait', str(args.wait),
           '--json']
    if args.org: imp += ['-o', args.org]
    ir = run_cmd(imp, capture_output=True)

    # on failure, parse actions and run suggested commands
    if ir.returncode != 0:
        err = {}
        try:
            err = json.loads(ir.stdout)
        except:
            pass
        actions = err.get('actions', [])
        for act in actions:
            m = re.search(r'"([^"]+)"', act)
            if m:
                cmd_str = m.group(1)
                parts = shlex.split(cmd_str)
                print(f"Fallback action: {cmd_str}")
                fb = run_cmd(parts, capture_output=True, cwd=bulk_dir)
                print(f"Output:\n{fb.stdout}\nError:\n{fb.stderr}")
        sys.exit(err.get('exitCode', 1))

    # success path: parse jobId
    res = json.loads(ir.stdout)
    job_id = res.get('result',{}).get('jobId')
    if not job_id:
        sys.stderr.write(f"ERROR: no jobId, stdout:\n{ir.stdout}\nerr:\n{ir.stderr}\n")
        sys.exit(1)
    print(f"Bulk import job started: {job_id}")

    # 4) results
    rcmd = ['sf','data','bulk','results','--job-id', job_id]
    if args.org: rcmd += ['-o', args.org]
    r2 = run_cmd(rcmd, capture_output=True, cwd=bulk_dir)
    if r2.returncode != 0:
        sys.stderr.write(f"ERROR results:\n{r2.stderr}\n")
        sys.exit(1)
    print(f"Bulk results in: {bulk_dir}")

if __name__=='__main__':
    main()
