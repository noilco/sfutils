#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_test_data.py

Salesforce “describe” JSON からテストデータ CSV を生成します。
Account オブジェクトの場合、`--person-rt-dev-name` で指定した
Record Type の DeveloperName に該当するレコードが個人取引先となり、

- 個人取引先では `__pc`、`LastName`、`FirstName`、`Salutation`、および `Person*` 項目に値を設定し、`Name` は空にします。
- 法人取引先では `Name` に値を設定し、個人専用項目（`__pc`、`LastName`、`FirstName`、`Salutation`、`Person*`）は空にします。

その他の項目生成はこれまで通り、Compound Field の Country/State ラベル、
依存ピックリスト、各種型対応（string/textarea, 数値、電話、email、URL、日付、日時、緯度/経度）などを考慮して行います。

Usage:
  python generate_test_data.py --describe describe.json \
      --rows 100 --out data.csv [--skip-fields F1,F2] \
      [--person-rt-dev-name PersonAccountDevName]
"""
import os
import json
import csv
import random
import string
import argparse
import base64
from datetime import date, datetime, timedelta, timezone
import sys

# 日本語文字プール
HIRAGANA = [chr(i) for i in range(0x3041, 0x3097)]
KATAKANA = [chr(i) for i in range(0x30A1, 0x30FB)]
KANJI    = [chr(i) for i in range(0x4E00, 0x9FFF)]
POOL_WEIGHTS = [0.45, 0.45, 0.10]
POOLS = [HIRAGANA, KATAKANA, KANJI]

# 定数
SYSTEM_FIELDS    = {"IsDeleted","CreatedById","CreatedDate","LastModifiedById","LastModifiedDate","SystemModstamp"}
EXCLUDE_RT_NAMES = {"マスター","マスタ"}
NUMERIC_TYPES    = {"double","currency","percent","int","integer"}
MIN_DATE = date(1700,1,1)
MAX_DATE = date(4000,12,31)
MIN_DT   = datetime(1700,1,1,tzinfo=timezone.utc)
MAX_DT   = datetime(4000,12,31,23,59,59,999000,tzinfo=timezone.utc)
DT_RANGE = (MAX_DT - MIN_DT).total_seconds()

# Helper functions

def random_japanese(length):
    # length: number of characters
    if length <= 0:
        return ''
    result = []
    for _ in range(length):
        pool = random.choices(POOLS, weights=POOL_WEIGHTS, k=1)[0]
        result.append(random.choice(pool))
    return ''.join(result)

def random_number(precision, scale):
    int_d = max(1, precision - scale)
    i = random.randint(0, 10**int_d - 1)
    if scale > 0:
        frac = ''.join(str(random.randint(0,9)) for _ in range(scale))
        return f"{i}.{frac}"
    return str(i)

def random_phone():
    if random.random() < 0.5:
        pre = random.choice(["090","080","070"])
    else:
        l = random.choice([2,3,4])
        pre = "0" + ''.join(random.choice(string.digits) for _ in range(l-1))
    mid = ''.join(random.choice(string.digits) for _ in range(4))
    last = ''.join(random.choice(string.digits) for _ in range(4))
    return f"{pre}-{mid}-{last}"

def random_email():
    l = random.randint(6,12)
    local = ''.join(random.choice(string.ascii_lowercase+string.digits) for _ in range(l))
    return f"{local}@example.com"

def random_url():
    l = random.randint(5,12)
    path = ''.join(random.choice(string.ascii_lowercase+string.digits) for _ in range(l))
    return f"https://example.com/{path}"

def random_date():
    d = MIN_DATE + timedelta(days=random.randint(0,(MAX_DATE-MIN_DATE).days))
    return d.strftime("%Y-%m-%d")

def random_datetime():
    dt = MIN_DT + timedelta(seconds=random.random()*DT_RANGE)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

def decode_valid_for(v):
    try:
        return base64.b64decode(v)
    except:
        return b''

def valid_for(vb, idx):
    return (vb[idx//8] >> (7 - (idx % 8)) & 1) if vb and idx//8 < len(vb) else 0

# parse arguments

def parse_args():
    p = argparse.ArgumentParser(description='Generate Salesforce test data CSV')
    p.add_argument('--describe', required=True, help='describe JSON file path')
    p.add_argument('--rows', type=int, default=10, help='number of rows to generate')
    p.add_argument('--skip-fields', default='', help='comma-separated fields to skip')
    p.add_argument('--out', required=True, help='output CSV path')
    p.add_argument('--person-rt-dev-name', help='DeveloperName of PersonAccount record type')
    return p.parse_args()

# main function

def main():
    args = parse_args()
    desc_path = os.path.abspath(args.describe)
    skips = {f.strip() for f in args.skip_fields.split(',') if f.strip()}
    with open(desc_path, encoding='utf-8') as f:
        meta = json.load(f).get('result')

    fields = [f for f in meta.get('fields', []) if not f.get('calculated') and f['name'] not in SYSTEM_FIELDS]
    rtinfos = [rt for rt in meta.get('recordTypeInfos', []) if rt.get('active') and rt.get('name') not in EXCLUDE_RT_NAMES]
    all_rts = [rt['recordTypeId'] for rt in rtinfos]
    id_to_dev = {rt['recordTypeId']: rt.get('developerName') for rt in rtinfos}
    print(f"Found {len(fields)} fields, {len(all_rts)} record types")

    # Prepare mappings
    ctrl_vals_map = {}
    dep_map = {}
    country_map = {}
    state_map = {}
    for fdef in fields:
        # dependent picklists
        ctrl = fdef.get('controllerName')
        if ctrl:
            if ctrl not in ctrl_vals_map:
                cont = next((x for x in fields if x['name']==ctrl), None)
                if cont:
                    ctrl_vals_map[ctrl] = [o['value'] for o in cont.get('picklistValues',[]) if 'value' in o]
            vals = ctrl_vals_map.get(ctrl, [])
            raw = fdef.get('picklistValues', [])
            vbs = [decode_valid_for(o.get('validFor','')) for o in raw]
            dep_map[fdef['name']] = {i: [o['value'] for vb,o in zip(vbs,raw) if valid_for(vb,i)] for i,_ in enumerate(vals)}
        # compound fields
        comp_raw = fdef.get('compoundFieldName') or ''
        if comp_raw.endswith('__c'):
            comp = comp_raw[:-3]
        elif comp_raw.endswith('Address'):
            comp = comp_raw[:-7]
        else:
            comp = ''
        if not comp:
            continue
        nm = fdef['name']
        api = nm[:-3] if nm.endswith('__s') else nm
        suffix = api[len(comp):] if api.startswith(comp) else ''
        suffix = suffix.lstrip('_')
        if suffix == 'CountryCode':
            country_map[comp] = [{'value':o['value'],'label':o['label']} for o in fdef.get('picklistValues',[]) if 'value' in o and 'label' in o]
        if suffix == 'StateCode':
            raw = fdef.get('picklistValues', [])
            mapping = {}
            for idx,_ in enumerate(country_map.get(comp, [])):
                mapping[idx] = [{'value':o['value'],'label':o['label']} for o in raw if valid_for(decode_valid_for(o.get('validFor','')), idx) and 'value' in o and 'label' in o]
            state_map[comp] = mapping

    # generate
    with open(args.out, 'w', newline='', encoding='utf-8') as out_f:
        writer = csv.DictWriter(out_f, fieldnames=[fld['name'] for fld in fields])
        writer.writeheader()
        for _ in range(args.rows):
            if all_rts:
                rt = random.choice(all_rts)
            else:
                rt = ''
            dev = id_to_dev.get(rt)
            is_person = (args.person_rt_dev_name and dev == args.person_rt_dev_name)
            row = {}
            comp_sel = {}
            for fdef in fields:
                nm = fdef['name']
                if not fdef.get('createable',True) or nm in skips:
                    row[nm] = ''
                    continue
                if nm == 'RecordTypeId':
                    row[nm] = rt; continue
                # Person* exclusive
                if nm.startswith('Person') and not is_person:
                    row[nm] = ''; continue
                # custom person code
                if nm.endswith('__pc'):
                    row[nm] = random_japanese(10) if is_person else ''; continue
                # Name / personal fields
                if nm == 'Name':
                    row[nm] = '' if is_person else random_japanese(min(int(fdef.get('length') or 10), 50)); continue
                if nm == 'LastName':
                    row[nm] = random_japanese(10) if is_person else ''; continue
                if nm == 'FirstName':
                    row[nm] = random_japanese(10) if is_person else ''; continue
                if nm == 'Salutation':
                    if is_person:
                        opts=[o['value'] for o in fdef.get('picklistValues',[]) if 'value' in o]
                        row[nm]=random.choice(opts) if opts else ''
                    else:
                        row[nm]=''
                    continue
                # compound address
                comp_raw = fdef.get('compoundFieldName') or ''
                if comp_raw.endswith('__c'):
                    comp=comp_raw[:-3]
                elif comp_raw.endswith('Address'):
                    comp=comp_raw[:-7]
                else:
                    comp=''
                api = nm[:-3] if nm.endswith('__s') else nm
                suffix = api[len(comp):] if api.startswith(comp) else ''
                suffix=suffix.lstrip('_')
                if comp and suffix=='CountryCode':
                    opts=country_map.get(comp,[])
                    choice=random.choice(opts) if opts else {'value':'','label':''}
                    row[nm]=choice['value']; comp_sel[comp]=choice; continue
                if comp and suffix=='Country':
                    row[nm]=comp_sel.get(comp,{}).get('label',''); continue
                if comp and suffix=='StateCode':
                    idx=next((i for i,e in enumerate(country_map.get(comp,[])) if e==comp_sel.get(comp)),0)
                    opts=state_map.get(comp,{}).get(idx,[])
                    choice=random.choice(opts) if opts else {'value':'','label':''}
                    row[nm]=choice['value']; comp_sel[comp+'_state']=choice; continue
                if comp and suffix=='State':
                    row[nm]=comp_sel.get(comp+'_state',{}).get('label',''); continue
                if comp and suffix=='City':
                    row[nm]=random_japanese(min(int(fdef.get('length') or 0),10) or 10); continue
                if comp and suffix=='PostalCode':
                    row[nm]=f"{random.randint(100,999)}-{random.randint(1000,9999)}"; continue
                if comp and suffix=='Street':
                    row[nm]=random_japanese(int(fdef.get('length') or 20)); continue
                # geolocation
                if suffix=='Latitude': row[nm]=f"{random.uniform(-90,90):.6f}"; continue
                if suffix=='Longitude': row[nm]=f"{random.uniform(-180,180):.6f}"; continue
                # dependent picklist
                ctrl=fdef.get('controllerName')
                if ctrl and row.get(ctrl) is not None:
                    vals=ctrl_vals_map.get(ctrl,[])
                    idx=vals.index(row[ctrl]) if row[ctrl] in vals else 0
                    opts=dep_map.get(nm,{}).get(idx,[])
                    row[nm]=random.choice(opts) if opts else ''; continue
                # handle types
                t=fdef.get('type','').lower()
                if t in ('string','textarea'):
                    max_len=int(fdef.get('length') or 0)
                    nillable=fdef.get('nillable',False)
                    min_len=0 if nillable else 1
                    length=random.randint(min_len,max_len) if max_len>0 else 0
                    row[nm]=random_japanese(length)
                    continue
                if t=='picklist':
                    opts=[o['value'] for o in fdef.get('picklistValues',[]) if 'value' in o]
                    row[nm]=random.choice(opts) if opts else ''
                    continue
                if t in ('multipicklist','multiselectpicklist'):
                    opts=[o['value'] for o in fdef.get('picklistValues',[]) if 'value' in o]
                    row[nm]=';'.join(random.sample(opts,random.randint(1,len(opts)))) if opts else ''
                    continue
                if t in NUMERIC_TYPES:
                    prec=int(fdef.get('precision') or 0); sc=int(fdef.get('scale') or 0)
                    row[nm]=random_number(prec,sc)
                    continue
                if t=='phone': row[nm]=random_phone(); continue
                if t=='email': row[nm]=random_email(); continue
                if t=='url': row[nm]=random_url(); continue
                if t=='date': row[nm]=random_date(); continue
                if t=='datetime': row[nm]=random_datetime(); continue
                row[nm]=''
            writer.writerow(row)

if __name__=='__main__': main()
