from pathlib import Path

from nlp_lab_sample_provenance.desk_cli import load_case


def test_measurement_only_inherits_pre_split_operation_from_same_batch():
    fixture = Path(__file__).parents[1] / 'fixtures'
    output = load_case(fixture / 'work.json', fixture / 'business.json')
    assert output[0]['eligible']
    assert output[0]['signed_inclusion']['analysis'] == 'AN-1'
    assert not output[1]['eligible']
    assert not output[2]['eligible']
