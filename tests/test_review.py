from pathlib import Path

from nlp_lab_sample_provenance.desk import review
from nlp_lab_sample_provenance.desk_cli import load_review

FIXTURES = Path(__file__).parents[1] / 'fixtures'


def _review():
    return load_review(FIXTURES / 'work.json', FIXTURES / 'business.json',
                       FIXTURES / 'records.json')


def _measurement(report, result_id):
    return next(item for item in report['measurements'] if item['result'] == result_id)


def test_alias_measurements_resolve_to_actual_aliquot():
    report = _review()
    meas4 = _measurement(report, 'MEAS-4')
    assert meas4['actual_sample'] == {'batch': 'B17', 'parent': 'X7', 'aliquot': 'X7-a'}
    assert meas4['eligible'] and meas4['status'] == 'stable'
    meas5 = _measurement(report, 'MEAS-5')
    assert meas5['actual_sample']['aliquot'] == 'X7-b'
    assert meas5['eligible']


def test_earlier_measurement_cannot_use_pre_split_handover():
    meas3 = _measurement(_review(), 'MEAS-3')
    assert not meas3['eligible']
    assert meas3['missing'] == ['已登记交接']
    assert '晚于测量' in meas3['exclusion_reason']
    handover = next(row for row in meas3['operations'] if row['label'] == '已登记交接')
    assert handover['via'] == '分装前继承' and not handover['usable']


def test_merge_groups_distinguish_usable_entries_under_two_names():
    groups = _review()['merge_groups']
    first = next(group for group in groups if group['actual_sample']['aliquot'] == 'X7-a')
    assert set(first['registered_names']) == {'X7-a', '第一管'}
    assert set(first['usable_together']) == {'MEAS-1', 'MEAS-4'}
    assert first['excluded'] == []
    rest = next(group for group in groups if group['actual_sample']['aliquot'] == 'X7-b')
    assert rest['usable_together'] == ['MEAS-5']
    assert rest['excluded'][0]['result'] == 'MEAS-3'


def test_conflicts_carry_original_text_and_open_points():
    conflicts = _review()['conflicts']
    early = next(item for item in conflicts if 'B17' in item['subject'])
    assert early['status'] == '时间不一致'
    assert early['explanation']['evidence']['record_id'] == 'lab-b'
    assert '仪器时间可能早于签字' in early['explanation']['evidence']['text']
    unmatched = next(item for item in conflicts if 'B18' in item['subject'])
    assert unmatched['status'] == '未对应'
    assert unmatched['undetermined']


def test_records_classified_pre_split_or_single_tube():
    records = _review()['records']
    handover = next(row for row in records if row['kind'] == 'handover')
    assert handover['classification'] == '分装前事件'
    assert handover['follows'] == '全部子样本'
    skipped = next(row for row in records if row['kind'] == 'no_handover')
    assert 'X7-b' in skipped['follows']
    instrument = next(row for row in records if row['record_id'] == 'lab-c')
    assert '未定' in instrument['classification']


def test_signed_inclusion_retained_with_basis_and_traceable():
    report = _review()
    signed = report['signed_inclusions'][0]
    assert signed['analysis'] == 'AN-1' and signed['result'] == 'MEAS-1'
    assert signed['basis']
    meas1 = _measurement(report, 'MEAS-1')
    assert meas1['signed_inclusion'] == signed
    assert {item['record_id'] for item in meas1['evidence']} >= {'lab-a', 'lab-e', 'lab-f'}


def test_case_level_undetermined_points_listed():
    points = _review()['undetermined']
    assert any('分装的具体时点' in point for point in points)
    assert any('未注明日期' in point for point in points)


def test_ambiguous_alias_requires_admin_verification():
    registry = {'samples': [{'batch': 'B1', 'sample': 'X7',
                             'children': ['X7-a', 'X7-b', 'X7-c']}],
                'signed_inclusions': []}
    case = {'required': [], 'operations': [],
            'measurements': [{'id': 'M1', 'batch': 'B1', 'sample': '剩下那管',
                              'at': '2026-11-18T10:00:00'}]}
    measurement = review(case, registry)['measurements'][0]
    assert measurement['status'] == 'needs_verification'
    assert measurement['affected'] == ['归属']
    assert len(measurement['interpretations']) == 2


def test_alias_interpretations_can_change_readiness():
    registry = {'samples': [{'batch': 'B1', 'sample': 'X7',
                             'children': ['X7-a', 'X7-b', 'X7-c']}],
                'signed_inclusions': []}
    case = {'required': ['已登记交接'],
            'operations': [{'batch': 'B1', 'container': 'X7-b', 'label': '已登记交接',
                            'at': '2026-11-18T09:00:00', 'before_split': False}],
            'measurements': [{'id': 'M1', 'batch': 'B1', 'sample': '剩下那管',
                              'at': '2026-11-18T10:00:00'}]}
    measurement = review(case, registry)['measurements'][0]
    assert measurement['status'] == 'needs_verification'
    assert '纳入就绪' in measurement['affected']


def test_conflicting_split_order_marks_attribution_affected():
    facts = [{'kind': 'split', 'batch': 'B1', 'parent': 'X7',
              'children': ['X7-b', 'X7-a'],
              'evidence': {'record_id': 'n1', 'source': 'lab-notebook', 'revision': 1,
                           'text': '批次 B1 样本 X7 分成 X7-b 与 X7-a。'}}]
    registry = {'samples': [{'batch': 'B1', 'sample': 'X7', 'children': ['X7-a', 'X7-b']}],
                'signed_inclusions': []}
    case = {'required': [], 'operations': [],
            'measurements': [{'id': 'M1', 'batch': 'B1', 'sample': '第一管',
                              'at': '2026-11-18T10:00:00'}]}
    measurement = review(case, registry, facts)['measurements'][0]
    assert measurement['status'] == 'needs_verification'
    assert '归属' in measurement['affected']
    assert {item['actual_sample']['aliquot'] for item in measurement['interpretations']} == {'X7-a', 'X7-b'}
