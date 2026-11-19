"""从中文笔记识别样本、分装关系、交接事件和相对时间。

每条抽取结果都保留来源记录（记录号、来源、修订号、原文）作为证据，
供经办人核对；无法识别的记录返回空事实列表，由调用方标记不能确定的点。
"""

import re

_SAMPLE = r'[A-Za-z]+\d+(?:-[A-Za-z0-9]+)*'
_CLOCK = r'\d{1,2}:\d{2}'
_TIME = rf'(?:\d{{4}}-\d{{2}}-\d{{2}}T{_CLOCK}(?::\d{{2}})?|{_CLOCK})'
_ALIAS = r'(?:第一管|剩下那管)'

_SPLIT_RE = re.compile(
    rf'批次\s*(?P<batch>{_SAMPLE})\s*样本\s*(?P<parent>{_SAMPLE})[^。；]*?分成\s*(?P<children>[^。；]+)')
_INSTRUMENT_RE = re.compile(
    rf'批次\s*(?P<batch>{_SAMPLE})\s*的\s*(?P<sample>{_SAMPLE})\s*记录\s*(?P<time>{_TIME})')
_HANDOVER_RE = re.compile(
    rf'(?P<mention>{_ALIAS}|{_SAMPLE})\s*(?P<time>{_TIME})?\s*已登记交接')
_NO_HANDOVER_RE = re.compile(rf'(?P<mention>{_ALIAS}|{_SAMPLE})\s*未交接')
_BEFORE_SPLIT_RE = re.compile(r'发生在分装前')
_SPLIT_TIMING_RE = re.compile(r'分装在(?P<claim>[^，。；]+)之后')
_SAMPLE_TOKEN_RE = re.compile(_SAMPLE)


def parse_record(record):
    """从单条记录抽取结构化事实，每个事实都带原文证据。"""
    evidence = {
        'record_id': record['record_id'],
        'source': record['source'],
        'revision': record['revision'],
        'text': record['text'],
    }
    text = record['text']
    facts = []
    match = _SPLIT_RE.search(text)
    if match:
        facts.append({
            'kind': 'split',
            'batch': match.group('batch'),
            'parent': match.group('parent'),
            'children': _SAMPLE_TOKEN_RE.findall(match.group('children')),
            'evidence': evidence,
        })
    match = _INSTRUMENT_RE.search(text)
    if match:
        facts.append({
            'kind': 'instrument',
            'batch': match.group('batch'),
            'sample': match.group('sample'),
            'time': match.group('time'),
            'evidence': evidence,
        })
    for match in _HANDOVER_RE.finditer(text):
        facts.append({
            'kind': 'handover',
            'mention': match.group('mention'),
            'time': match.group('time'),
            'label': '已登记交接',
            'evidence': evidence,
        })
    for match in _NO_HANDOVER_RE.finditer(text):
        facts.append({
            'kind': 'no_handover',
            'mention': match.group('mention'),
            'evidence': evidence,
        })
    if _BEFORE_SPLIT_RE.search(text):
        facts.append({'kind': 'before_split', 'evidence': evidence})
    claims = []
    timing = _SPLIT_TIMING_RE.search(text)
    if timing:
        claims.append((timing.start(), f"分装在{timing.group('claim')}之后"))
    index = text.find('仪器时间可能早于签字')
    if index >= 0:
        claims.append((index, '仪器时间可能早于签字'))
    if claims:
        facts.append({'kind': 'note', 'claims': [claim for _, claim in sorted(claims)],
                      'evidence': evidence})
    return {
        'record_id': record['record_id'],
        'source': record['source'],
        'revision': record['revision'],
        'text': text,
        'facts': facts,
    }


def parse_records(records):
    return [parse_record(record) for record in records]


def flatten_facts(parsed):
    return [fact for record in parsed for fact in record['facts']]
