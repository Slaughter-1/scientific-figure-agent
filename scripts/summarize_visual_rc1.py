import argparse
import json
from pathlib import Path
from figure_agent.visual_eval import summarize_reviews

parser = argparse.ArgumentParser()
parser.add_argument('scores', type=Path)
parser.add_argument('--frozen', type=Path, default=Path('outputs/visual-benchmark-rc1'))
args = parser.parse_args()
payload = json.loads(args.scores.read_text(encoding='utf-8'))
expected = json.loads((args.frozen / 'reviewer/blank-scores.json').read_text(encoding='utf-8'))
expected_ids = {r['blind_id']:r['paper_width'] for r in expected['rows']}
actual_ids = {r['blind_id']:r['paper_width'] for r in payload['rows']}
if expected_ids != actual_ids or len(payload['rows']) != 120:
    raise SystemExit('Scores do not match the frozen 120 review conditions.')
payload['row_count'] = 120
print(json.dumps(summarize_reviews(payload), ensure_ascii=False, indent=2))
