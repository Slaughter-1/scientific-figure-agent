"""Freeze existing outputs; never invokes a renderer or changes a candidate."""
import hashlib
import html
import json
import random
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def write(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    output = ROOT / 'outputs/visual-benchmark-rc1'
    if output.exists():
        raise SystemExit('Frozen directory already exists; do not overwrite RC1.')
    source = ROOT / 'outputs/visual-benchmark'
    cases = json.loads((ROOT / 'eval_cases/visual_quality/benchmark_20.json').read_text(encoding='utf-8'))
    records = sorted(source.glob('*/candidate_*/candidate.json'))
    if len(cases) != 20 or len(records) != 60:
        raise SystemExit('Expected exactly 20 cases / 60 candidates.')
    shutil.copytree(source, output / 'snapshot')
    # Preserve the original dataset including historical attribution; corrected
    # provenance is separate, rather than silently rewriting frozen input.
    shutil.copy2(ROOT / 'eval_cases/visual_quality/benchmark_20.json', output / 'cases-original.json')
    for case in cases:
        case['gold_source'] = 'ai_authored_synthetic'
        case['human_verified'] = False
    write(output / 'cases-provenance-corrected.json', cases)
    blind = output / 'reviewer'
    (blind / 'images').mkdir(parents=True)
    combinations = [(record, width) for record in records for width in ('single_column', 'double_column')]
    random.Random(20260921).shuffle(combinations)
    private, rows, sections = [], [], []
    metrics = ['semantic_correct','no_overlap_or_clipping','text_readability','arrow_clarity','information_hierarchy','paper_aesthetics']
    failures = ['semantic_error','missing_relation','wrong_direction','missing_condition','overlap','clipping','edge_cross_node','unreadable_text']
    for index, (record, width) in enumerate(combinations, 1):
        candidate = json.loads(record.read_text(encoding='utf-8'))
        case = next(c for c in cases if c['id'] == record.parent.parent.name)
        identity = f'B{index:03d}'
        png = Path(candidate['artifacts']['png'])
        if not png.is_absolute():
            png = ROOT / png
        shutil.copy2(png, blind / 'images' / f'{identity}.png')
        private.append({'blind_id':identity,'case_id':case['id'],'candidate_id':candidate['candidate_id'], 'revision_id':candidate['revision_id'],'paper_width':width,'png_sha256':hashlib.sha256(png.read_bytes()).hexdigest()})
        rows.append({'blind_id':identity,'paper_width':width,**{key:None for key in metrics},'hard_failures':[],'notes':'','reviewer':'','reviewed_at':''})
        controls = ''.join(f'<label>{metric}<input type="number" min="1" max="5" step="0.5" data-field="{metric}"></label>' for metric in metrics)
        checks = ''.join(f'<label><input type="checkbox" value="{code}">{code}</label>' for code in failures)
        sections.append(f'<section data-id="{identity}"><h2>{identity} / {width}</h2><p>原始输入：{html.escape(case["text"])}</p><img src="images/{identity}.png" style="width:{85 if width=="single_column" else 180}mm" alt="{identity}"><div class="controls">{controls}</div><div>{checks}</div><textarea placeholder="评审备注"></textarea></section>')
    write(output / 'private-mapping.json', private)
    write(blind / 'blank-scores.json', {'row_count':120,'rows':rows})
    page = '''<!doctype html><html lang="zh"><meta charset="utf-8"><title>RC1 盲评</title>
<style>body{font:15px sans-serif;margin:32px;color:#172033}section{border-top:1px solid #ccc;padding:24px 0;break-before:page}img{display:block;max-width:none}.controls{display:flex;gap:12px;flex-wrap:wrap}label{display:inline-block;margin:8px}input[type=number]{width:55px}textarea{display:block;width:80%;height:50px}header{position:sticky;top:0;background:white;padding:12px} @media print{header,.controls,textarea,input{display:none}}</style>
<header>匿名评审：只向评审员发 reviewer 目录。源案例由 AI 编写，需独立判断语义，不使用参考答案或自动分数。<br>浏览器缩放 100%，以打印 100% 比例核对 85mm / 180mm；屏幕物理尺寸取决于显示器。<br><label>评审员<input id="reviewer"></label><button id="save">下载评分 JSON</button><span id="message"></span></header>
''' + ''.join(sections) + '<script>const payload=' + json.dumps({'row_count':120,'rows':rows}, ensure_ascii=False) + ''';
document.querySelector('#save').onclick=()=>{const reviewer=document.querySelector('#reviewer').value.trim();if(!reviewer){alert('请输入评审员标识');return;}for(const s of document.querySelectorAll('section')){const r=payload.rows.find(r=>r.blind_id===s.dataset.id);for(const input of s.querySelectorAll('[data-field]'))r[input.dataset.field]=input.value===''?null:Number(input.value);r.hard_failures=Array.from(s.querySelectorAll('input[type=checkbox]:checked')).map(x=>x.value);r.notes=s.querySelector('textarea').value;r.reviewer=reviewer;r.reviewed_at=Object.keys(r).filter(k=>s.querySelector('[data-field="'+k+'"]')).every(k=>r[k]!==null)?new Date().toISOString():'';}const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='rc1-scores.json';a.click();URL.revokeObjectURL(url);};</script></html>'''
    (blind / 'index.html').write_text(page, encoding='utf-8')
    write(output / 'protocol.json', {'frozen_at':datetime.now(timezone.utc).isoformat(),'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'working_tree':'uncommitted_changes_present', 'column_width_mm':{'single_column':85,'double_column':180}, 'thresholds':{'text_readability_mean':4.5,'arrow_clarity_mean':4.3,'paper_aesthetics_mean':4.0},'hard_failures_allowed':0,'human_scored_count':0,'human_gate':'pending','case_provenance':'AI-authored synthetic, not independently annotated paper gold'})
    files = [{'path':p.relative_to(output).as_posix(),'size_bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(output.rglob('*')) if p.is_file()]
    write(output / 'freeze-manifest.json', {'files':files})
    for entry in files:
        assert hashlib.sha256((output / entry['path']).read_bytes()).hexdigest() == entry['sha256']
    print(f'Frozen {len(records)} candidates; {len(rows)} anonymous conditions; {len(files)} hashes verified.')


if __name__ == '__main__':
    main()
