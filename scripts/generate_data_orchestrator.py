#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_data_orchestrator.py

指定オブジェクトの定義取得からテストデータ作成、Bulk API インポートまでを
ワンストップで実行するスクリプト。
--skip-import オプション指定で CSV 作成のみを行い、インポートはスキップします。

Usage:
  python generate_data_orchestrator.py \
      --object Account \
      --rows 100 \
      --skip-import \
      [--skip-fields Field1,Field2] \
      [--person-rt-dev-name DevName] \
      [--org alias] \
      [--line-ending LF|CRLF] \
      [--wait minutes]
"""
import subprocess
import argparse
import sys
import os
import json
import re
import shlex
import shutil

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT_PATH = os.path.join(SCRIPT_DIR, 'generate_test_data.py')
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))
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
    shell = os.name == 'nt'
    if isinstance(cmd, (list, tuple)) and cmd:
      exe = cmd[0]
      path = shutil.which(exe)
      if path:
          cmd[0] = path

    return subprocess.run(
        cmd,
        cwd=cwd or PROJECT_ROOT,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.PIPE,
        text=True
    )


def main():
    p = argparse.ArgumentParser(description='Orchestrate test-data generation and bulk import')
    p.add_argument('--object', required=True, help='SObject API name')
    p.add_argument('--rows', type=int, required=True, help='Number of rows to generate')
    p.add_argument('--skip-fields', default='', help='Fields to skip (comma-separated)')
    p.add_argument('--person-rt-dev-name', default=None, help='DeveloperName of PersonAccount record type')
    p.add_argument('--org', default=None, help='Org alias for sf CLI')
    p.add_argument('--line-ending', choices=['LF','CRLF'], default='CRLF', help='CSV line ending')
    p.add_argument('--wait', type=int, default=10, help='Bulk wait minutes')
    p.add_argument('--skip-import', action='store_true', help='Generate CSV only, skip bulk import')
    args = p.parse_args()

    desc_dir, data_dir, bulk_dir = init_output_dirs()

    # 1) Describe
    desc_path = os.path.join(desc_dir, f"{args.object}.json")
    cmd_desc = ['sf','sobject','describe','--sobject',args.object,'--json']
    if args.org:
        cmd_desc += ['-u', args.org]
    res = run_cmd(cmd_desc, capture_output=True)
    if res.returncode != 0:
        sys.stderr.write(f"Error describing: {res.stderr}\n")
        sys.exit(1)
    with open(desc_path, 'w', encoding='utf-8') as f:
        f.write(res.stdout)
    print(f"Describe saved to {desc_path}")

    # 2) Generate CSV
    data_path = os.path.join(data_dir, f"{args.object}.csv")
    gen_cmd = [sys.executable, SCRIPT_PATH,
               '--describe', desc_path,
               '--rows', str(args.rows),
               '--out', data_path]
    if args.skip_fields:
        gen_cmd += ['--skip-fields', args.skip_fields]
    if args.person_rt_dev_name:
        gen_cmd += ['--person-rt-dev-name', args.person_rt_dev_name]
    print(f"gen cmd : {' '.join(gen_cmd)}")
    g = run_cmd(gen_cmd, capture_output=True)
    if g.returncode != 0:
        sys.stderr.write(f"Error generating data: {g.stderr}\n")
        sys.exit(1)
    print(f"Test data generated: {data_path}")

    # 2.5) Skip import if requested
    if args.skip_import:
        print("--skip-import specified, skipping bulk import.")
        sys.exit(0)

    # 3) Bulk import
    imp_cmd = ['sf','data','import','bulk',
               '--sobject', args.object,
               '--file', data_path,
               '--line-ending', args.line_ending,
               '--wait', str(args.wait),
               '--json']
    if args.org:
        imp_cmd += ['-o', args.org]
    imp_res = run_cmd(imp_cmd, capture_output=True)

    # On failure, execute fallback actions
    if imp_res.returncode != 0:
        try:
            err = json.loads(imp_res.stdout)
            actions = err.get('actions', [])
        except:
            actions = []
        for act in actions:
            m = re.search(r'"([^"]+)"', act)
            if m:
                fb_cmd = shlex.split(m.group(1))
                fb_res = run_cmd(fb_cmd, capture_output=True, cwd=bulk_dir)
                print(f"Executed fallback: {fb_cmd}\nOut: {fb_res.stdout}\nErr: {fb_res.stderr}")
        sys.exit(err.get('exitCode', 1))

    # 4) Retrieve results
    res_json = json.loads(imp_res.stdout)
    job_id = res_json.get('result', {}).get('jobId')
    if not job_id:
        sys.stderr.write(f"No jobId returned: {imp_res.stdout}\n")
        sys.exit(1)
    print(f"Bulk job started: {job_id}")

    res_cmd = ['sf','data','bulk','results','--job-id', job_id]
    if args.org:
        res_cmd += ['-o', args.org]
    r2 = run_cmd(res_cmd, capture_output=True, cwd=bulk_dir)
    if r2.returncode != 0:
        sys.stderr.write(f"Error retrieving results: {r2.stderr}\n")
        sys.exit(1)
    print(f"Results saved under {bulk_dir}")

if __name__ == '__main__':
    main()
