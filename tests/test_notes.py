import json
from pathlib import Path

from nlp_lab_sample_provenance.notes import flatten_facts, parse_records
from nlp_lab_sample_provenance.repository import JsonRepository
from nlp_lab_sample_provenance.workflow import TextWorkflow

FIXTURES = Path(__file__).parents[1] / 'fixtures'


def _facts():
    records = json.loads((FIXTURES / 'records.json').read_text(encoding='utf-8'))
    return flatten_facts(parse_records(records))


def test_split_fact_keeps_original_text_as_evidence():
    split = [fact for fact in _facts() if fact['kind'] == 'split']
    assert len(split) == 1
    assert split[0]['batch'] == 'B17'
    assert split[0]['parent'] == 'X7'
    assert split[0]['children'] == ['X7-a', 'X7-b']
    assert split[0]['evidence']['record_id'] == 'lab-a'
    assert '分成' in split[0]['evidence']['text']


def test_handover_note_uses_alias_and_clock_time():
    handover = [fact for fact in _facts() if fact['kind'] == 'handover']
    assert len(handover) == 1
    assert handover[0]['mention'] == '第一管'
    assert handover[0]['time'] == '10:00'
    skipped = [fact for fact in _facts() if fact['kind'] == 'no_handover']
    assert skipped[0]['mention'] == '剩下那管'


def test_two_instrument_logs_share_duplicate_sample_number():
    instrument = [fact for fact in _facts() if fact['kind'] == 'instrument']
    assert {(fact['batch'], fact['sample']) for fact in instrument} == {('B17', 'X7'), ('B18', 'X7')}
    assert {fact['time'] for fact in instrument} == {'09:50', '14:03'}


def test_supplement_marks_handover_before_split():
    assert any(fact['kind'] == 'before_split' and fact['evidence']['record_id'] == 'lab-f'
               for fact in _facts())


def test_correction_claims_keep_text_order():
    note = [fact for fact in _facts() if fact['kind'] == 'note']
    assert note[0]['claims'] == ['分装在三次冻融之后', '仪器时间可能早于签字']


def test_workflow_note_facts_reads_ingested_records(tmp_path):
    workflow = TextWorkflow(JsonRepository(tmp_path / 'records.json'))
    workflow.ingest([{'record_id': 'r1', 'source': 'lab-notebook', 'revision': 1,
                      'text': '批次 B17 样本 X7 解冻一次后分成 X7-a 与 X7-b。'}])
    parsed = workflow.note_facts()
    assert parsed[0]['facts'][0]['kind'] == 'split'
    assert parsed[0]['facts'][0]['children'] == ['X7-a', 'X7-b']
