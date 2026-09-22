import copy
import hashlib
import json
from pathlib import Path

import pytest

from figure_agent.license import check_export_license
from figure_agent.visual_eval import RUBRIC, summarize_reviews


def audited_asset(tmp_path):
    content = tmp_path / 'icon.svg'
    evidence = tmp_path / 'LICENSE'
    content.write_text('<svg/>')
    evidence.write_text('Test fixture license evidence')
    return {'asset_id': 'fixture', 'source': 'test', 'source_url': 'https://example.org/icon.svg',
            'license': 'MIT', 'license_evidence_url': 'https://example.org/LICENSE',
            'retrieved_at': '2026-09-21T00:00:00+00:00', 'approval_status': 'approved',
            'path': str(content), 'license_evidence_path': str(evidence), 'hash_scope': 'file_bytes',
            'content_sha256': hashlib.sha256(content.read_bytes()).hexdigest(),
            'license_evidence_sha256': hashlib.sha256(evidence.read_bytes()).hexdigest()}


def test_asset_changes_cannot_inherit_old_url_approval(tmp_path):
    asset = audited_asset(tmp_path)
    assert check_export_license({'asset_refs': [asset]}) == []
    Path(asset['path']).write_text('<svg><rect/></svg>')
    assert 'content_identity_mismatch' in {x['code'] for x in check_export_license({'asset_refs': [asset]})}


@pytest.mark.parametrize('status', ['unknown', 'rejected', 'review_required', '', 'banana', None])
def test_only_explicit_approval_can_pass(tmp_path, status):
    asset = audited_asset(tmp_path)
    asset['approval_status'] = status
    assert check_export_license({'asset_refs': [asset]})


def test_asset_evidence_cannot_be_null_or_changed(tmp_path):
    asset = audited_asset(tmp_path)
    asset['license_evidence_url'] = None
    assert check_export_license({'asset_refs': [asset]})
    asset = audited_asset(tmp_path)
    Path(asset['license_evidence_path']).write_text('different license')
    assert check_export_license({'asset_refs': [asset]})


def test_visual_means_are_separate_and_invalid_scores_fail_closed():
    rows = [{ 'blind_id': str(i), 'paper_width': width, 'reviewer': 'tester', 'reviewed_at': '2026-09-21T12:00:00+00:00',
              **{metric: 5 for metric in RUBRIC}, 'hard_failures': []}
            for i, width in enumerate(['single_column','double_column'])]
    payload = {'row_count': 2, 'rows': rows}
    rows[0]['text_readability'] = 3.2
    result = summarize_reviews(payload)
    assert not result['release_ready']
    assert result['by_paper_width']['single_column']['mean_readability'] == 3.2
    rows[0]['text_readability'] = 99
    assert not summarize_reviews(payload)['release_ready']


def test_partial_duplicate_or_unscored_reviews_cannot_pass():
    row = {'blind_id': 'a', 'paper_width': 'single_column', 'reviewer': 'tester', 'reviewed_at': '2026-09-21T12:00:00+00:00', **{m: 5 for m in RUBRIC}, 'hard_failures': []}
    assert not summarize_reviews({'row_count':120,'rows':[row]})['release_ready']
    assert not summarize_reviews({'row_count':2,'rows':[row,copy.deepcopy(row)]})['release_ready']
