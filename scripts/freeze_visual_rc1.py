"""Freeze existing outputs; never invokes a renderer or changes a candidate."""
import hashlib
import html
import json
import random
import shutil
import struct
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def write(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


#: Fields that must never reach the reviewer directory.
LEAKY_FIELDS = ('case_id', 'candidate_id', 'revision_id', 'recommend', 'heuristic', 'scores', 'spec_sha256')


def assert_reviewer_package_is_blind(reviewer_dir):
    """Refuse to ship a review package that carries identity or machine scores."""
    for path in sorted(Path(reviewer_dir).rglob('*')):
        if not path.is_file() or path.suffix.lower() not in {'.json', '.html', '.csv'}:
            continue
        text = path.read_text(encoding='utf-8', errors='replace')
        leaked = [field for field in LEAKY_FIELDS if field in text]
        if leaked:
            raise SystemExit(f'Reviewer package leaks {leaked} in {path.name}; fix before sending.')


#: Physical width of each review condition, in millimetres.
COLUMN_WIDTH_MM = {'single_column': 85.0, 'double_column': 180.0}


def measure_png_mm(path, dpi=220):
    """Read real pixel dimensions from the PNG IHDR, not a self-reported field."""
    data = Path(path).read_bytes()
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise SystemExit(f'Not a PNG: {path}')
    width_px, height_px = struct.unpack('>II', data[16:24])
    return {'width_px': width_px, 'height_px': height_px,
            'width_mm': round(width_px / dpi * 25.4, 2), 'height_mm': round(height_px / dpi * 25.4, 2)}


def normalize_cases(raw_cases):
    """Normalize legacy id/text lists and the validated S5 cases envelope."""
    if isinstance(raw_cases, dict) and isinstance(raw_cases.get('cases'), list):
        raw_cases = raw_cases['cases']
    if not isinstance(raw_cases, list):
        raise SystemExit('Cases input must be a list or an envelope containing cases[].')
    cases = []
    for item in raw_cases:
        if not isinstance(item, dict):
            raise SystemExit('Each case must be an object.')
        case_id = item.get('id') or item.get('task_id')
        text = item.get('text') or item.get('source_text')
        if not case_id or not text:
            raise SystemExit('Each case must provide id/text or task_id/source_text.')
        normalized = dict(item)
        normalized['id'] = case_id
        normalized['text'] = text
        cases.append(normalized)
    return cases


def main(round_id='rc1', seed=20260921, source=None, cases_path=None, widths=('single_column', 'double_column')):
    output = ROOT / f'outputs/visual-benchmark-{round_id}'
    if output.exists():
        raise SystemExit(f'Frozen directory already exists; do not overwrite {round_id.upper()}.')
    source = Path(source) if source else ROOT / 'outputs/visual-benchmark'
    if not source.is_absolute():
        source = ROOT / source
    if not source.is_dir():
        raise SystemExit(f'Benchmark source directory not found: {source}')
    cases_path = Path(cases_path) if cases_path else ROOT / 'eval_cases/visual_quality/benchmark_20.json'
    if not cases_path.is_absolute():
        cases_path = ROOT / cases_path
    cases = normalize_cases(json.loads(cases_path.read_text(encoding='utf-8')))
    unsupported = [width for width in widths if width not in COLUMN_WIDTH_MM]
    if unsupported:
        raise SystemExit(f'Unsupported column width(s): {unsupported}.')
    # One real artifact set per width: <case>/<paper_width>/candidate_XX/candidate.json.
    records = sorted(record for record in source.glob('*/*/candidate_*/candidate.json')
                     if record.parent.parent.name in widths)
    expected = len(cases) * 3 * len(widths)
    if len(records) != expected:
        raise SystemExit(f'Expected {len(cases)} cases x 3 candidates x {len(widths)} widths = {expected} '
                         f'per-width candidates under {source}; found {len(records)}. '
                         'Generate with generate_benchmark(..., paper_widths=...) so each width is rendered separately.')
    shutil.copytree(source, output / 'snapshot')
    # Preserve the original dataset including historical attribution; corrected
    # provenance is separate, rather than silently rewriting frozen input.
    shutil.copy2(cases_path, output / 'cases-original.json')
    for case in cases:
        case['gold_source'] = 'ai_authored_synthetic'
        case['human_verified'] = False
    write(output / 'cases-provenance-corrected.json', cases)
    blind = output / 'reviewer'
    (blind / 'images').mkdir(parents=True)
    # Each record IS one width's real artifact set, so the condition is read from
    # the path. The previous cross product paired every record with both widths,
    # which is what forced one PNG to stand in for two physical sizes.
    combinations = [(record, record.parent.parent.name) for record in records]
    random.Random(seed).shuffle(combinations)
    private, rows, sections = [], [], []
    metrics = ['semantic_correct','no_overlap_or_clipping','text_readability','arrow_clarity','information_hierarchy','paper_aesthetics']
    failures = ['semantic_error','missing_relation','wrong_direction','missing_condition','overlap','clipping','edge_cross_node','unreadable_text']
    seen_bytes = {}
    for index, (record, width) in enumerate(combinations, 1):
        candidate = json.loads(record.read_text(encoding='utf-8'))
        case = next(c for c in cases if c['id'] == record.parent.parent.parent.name)
        identity = f'B{index:03d}'
        png = Path(candidate['artifacts']['png'])
        if not png.is_absolute():
            png = ROOT / png
        measured = measure_png_mm(png)
        expected_mm = COLUMN_WIDTH_MM[width]
        # Refuse to freeze a condition whose real pixels do not match its label.
        if abs(measured['width_mm'] - expected_mm) > 1.0:
            raise SystemExit(f'{record}: {width} artifact measures {measured["width_mm"]}mm '
                             f'({measured["width_px"]}px @220dpi) but {expected_mm}mm was expected. '
                             'The artifact was not generated at this column width.')
        digest = hashlib.sha256(png.read_bytes()).hexdigest()
        clash = seen_bytes.get(digest)
        if clash and clash[1] != width:
            raise SystemExit(f'{record}: identical PNG bytes shared by {clash[1]} and {width} '
                             f'(sha256 {digest[:12]}); the two widths were not generated separately.')
        seen_bytes[digest] = (record, width)
        shutil.copy2(png, blind / 'images' / f'{identity}.png')
        private.append({'blind_id':identity,'case_id':case['id'],'candidate_id':candidate['candidate_id'], 'revision_id':candidate['revision_id'],'paper_width':width,'paper_width_mm':expected_mm,'measured':measured,'source_candidate':record.relative_to(source).as_posix(),'png_sha256':digest})
        rows.append({'blind_id':identity,'paper_width':width,**{key:None for key in metrics},'hard_failures':[],'notes':'','reviewer':'','reviewed_at':''})
        controls = ''.join(f'<label>{metric}<input type="number" min="1" max="5" step="0.5" data-field="{metric}"></label>' for metric in metrics)
        checks = ''.join(f'<label><input type="checkbox" value="{code}">{code}</label>' for code in failures)
        # The PNG is itself generated at this column width, so the CSS width only
        # presents the artifact at its own measured physical size. It is not
        # rescaling one shared figure into a second condition.
        sections.append(f'<section data-id="{identity}"><h2>{identity} / {width}</h2><p>原始输入：{html.escape(case["text"])}</p><img src="images/{identity}.png" style="width:{measured["width_mm"]}mm" alt="{identity}"><p class="meta">按栏宽实际生成：{measured["width_px"]}×{measured["height_px"]} px @220dpi = {measured["width_mm"]}×{measured["height_mm"]} mm</p><div class="controls">{controls}</div><div>{checks}</div><textarea placeholder="评审备注"></textarea></section>')
    write(output / 'private-mapping.json', private)
    write(blind / 'blank-scores.json', {'row_count':len(rows),'rows':rows})
    page = '''<!doctype html><html lang="zh"><meta charset="utf-8"><title>RC1 盲评</title>
<style>body{font:15px sans-serif;margin:32px;color:#172033}section{border-top:1px solid #ccc;padding:24px 0;break-before:page}img{display:block;max-width:none}.controls{display:flex;gap:12px;flex-wrap:wrap}label{display:inline-block;margin:8px}input[type=number]{width:55px}textarea{display:block;width:80%;height:50px}.meta{font-size:12px;color:#5a6472}header{position:sticky;top:0;background:white;padding:12px} @media print{header,.controls,textarea,input{display:none}}</style>
<header>匿名评审：只向评审员发 reviewer 目录。源案例由 AI 编写，需独立判断语义，不使用参考答案或自动分数。<br>浏览器缩放 100%，以打印 100% 比例核对 85mm / 180mm；屏幕物理尺寸取决于显示器。<br><label>评审员<input id="reviewer"></label><button id="save">下载评分 JSON</button><span id="message"></span></header>
''' + ''.join(sections) + '<script>const payload=' + json.dumps({'row_count':len(rows),'rows':rows}, ensure_ascii=False) + ''';
document.querySelector('#save').onclick=()=>{const reviewer=document.querySelector('#reviewer').value.trim();if(!reviewer){alert('请输入评审员标识');return;}for(const s of document.querySelectorAll('section')){const r=payload.rows.find(r=>r.blind_id===s.dataset.id);for(const input of s.querySelectorAll('[data-field]'))r[input.dataset.field]=input.value===''?null:Number(input.value);r.hard_failures=Array.from(s.querySelectorAll('input[type=checkbox]:checked')).map(x=>x.value);r.notes=s.querySelector('textarea').value;r.reviewer=reviewer;r.reviewed_at=Object.keys(r).filter(k=>s.querySelector('[data-field="'+k+'"]')).every(k=>r[k]!==null)?new Date().toISOString():'';}const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='rc1-review-ratings.json';a.click();URL.revokeObjectURL(url);};</script></html>'''
    (blind / 'index.html').write_text(page, encoding='utf-8')
    measured_by_width = {width: sorted({entry['measured']['width_px'] for entry in private if entry['paper_width'] == width}) for width in widths}
    write(output / 'protocol.json', {'protocol_id':'S5-Agent-v1','evaluation_mode':'context_isolated_ai_visual_review','reviewer_type':'ai_agent','human_reviewed':False,'human_review_required':False,'frozen_at':datetime.now(timezone.utc).isoformat(),'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'working_tree':'uncommitted_changes_present', 'column_width_mm':{width: COLUMN_WIDTH_MM[width] for width in widths}, 'thresholds':{'text_readability_mean':4.5,'arrow_clarity_mean':4.3,'paper_aesthetics_mean':4.0},'hard_failures_allowed':0,'human_scored_count':0,'human_gate':'not_run','case_provenance':'AI-authored synthetic, isolated Curator; not independently annotated paper gold',
                                     'artifact_source':{'benchmark_dir':source.as_posix(),'cases':cases_path.as_posix(),'layout':'<case>/<paper_width>/candidate_XX','per_width_generation':True},
                                     'column_width_evidence':{'method':'PNG IHDR pixel width read from artifact bytes at 220 dpi','observed_png_width_px':measured_by_width,'distinct_bytes_per_width_verified':True,'display_scaling_used_as_substitute':False}})
    files = [{'path':p.relative_to(output).as_posix(),'size_bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(output.rglob('*')) if p.is_file()]
    assert_reviewer_package_is_blind(blind)
    write(output / 'freeze-manifest.json', {'files':files})
    for entry in files:
        assert hashlib.sha256((output / entry['path']).read_bytes()).hexdigest() == entry['sha256']
    print(f'Frozen {len(records)} per-width candidates; {len(rows)} anonymous conditions; {len(files)} hashes verified.')
    for width in widths:
        print(f'  {width}: {sum(entry["paper_width"] == width for entry in private)} conditions at {COLUMN_WIDTH_MM[width]}mm, PNG width {measured_by_width[width]} px')


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Freeze a review round; never re-renders candidates.')
    parser.add_argument('--round', default='rc1', help='round id, e.g. rc1 or r2')
    parser.add_argument('--seed', type=int, default=20260921, help='shuffle seed; record it in the report')
    parser.add_argument('--source', help='benchmark run directory laid out as <case>/<paper_width>/candidate_XX')
    parser.add_argument('--cases', help='case JSON used for that run')
    parser.add_argument('--widths', default='single_column,double_column', help='comma-separated column widths to freeze')
    args = parser.parse_args()
    main(round_id=args.round, seed=args.seed, source=args.source, cases_path=args.cases,
         widths=tuple(item.strip() for item in args.widths.split(',') if item.strip()))
