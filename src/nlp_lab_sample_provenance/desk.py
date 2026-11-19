"""核对台：按登记标签与实际测量时点核对归属、纳入范围与可合并结果。

核对结论可回查到笔记原文、时间和样本关系；已签分析登记独立保留，
不随当前建议改动。只核对本地合成资料的归属。
"""

from .provenance import Attribution


def _clock(value):
    """登记时间或笔记钟点的 HH:MM 部分，用于同日对照。"""
    return value[11:16] if isinstance(value, str) and 'T' in value else value


def assess(case, registry, facts=None):
    """每次测量的纳入核对列表（兼容旧用法）。"""
    return review(case, registry, facts)['measurements']


def review(case, registry, facts=None):
    """完整核对报告：归属、纳入、可合并结果、冲突与不能确定的点。"""
    facts = list(facts or [])
    attribution = Attribution(registry['samples'], facts)
    events = _resolve_events(facts, attribution)
    signed = {item['result']: item for item in registry.get('signed_inclusions', [])}
    measurements = [
        _review_measurement(measurement, case, attribution, events, signed)
        for measurement in case['measurements']
    ]
    _mark_merge(measurements)
    return {
        'required': list(case['required']),
        'measurements': measurements,
        'merge_groups': _merge_groups(measurements),
        'records': _classify_facts(facts, events),
        'conflicts': _conflicts(case, facts),
        'undetermined': _undetermined(case, facts, events, measurements),
        'signed_inclusions': list(registry.get('signed_inclusions', [])),
    }


def _review_measurement(measurement, case, attribution, events, signed):
    batch = measurement['batch']
    name = measurement['sample']
    base = {
        'result': measurement['id'],
        'batch': batch,
        'registered_as': name,
        'at': measurement['at'],
        'signed_inclusion': signed.get(measurement['id']),
    }
    interpretations = attribution.resolve(batch, name)
    if not interpretations:
        return {**base, 'actual_sample': None, 'eligible': False,
                'missing': sorted(case['required']), 'operations': [], 'evidence': [],
                'status': 'needs_verification', 'affected': ['归属'],
                'recommendation': f"名字「{name}」在批次 {batch} 未登记，请管理员核对",
                'undetermined': [f'名字「{name}」在批次 {batch} 未登记'],
                'merge_with': []}
    outcomes = [_outcome(measurement, item, case, events) for item in interpretations]
    primary = outcomes[0]
    affected = []
    if any(item['actual_sample'] != primary['actual_sample'] for item in outcomes):
        affected.append('归属')
    if any(item['eligible'] != primary['eligible'] for item in outcomes):
        affected.append('纳入就绪')
    status = 'stable' if not affected else 'needs_verification'
    recommendation = ('归属与纳入就绪在全部解释下一致，可继续选取' if status == 'stable'
                      else f"以下条件受影响：{'、'.join(affected)}，请管理员核对")
    return {
        **base,
        'actual_sample': primary['actual_sample'],
        'eligible': primary['eligible'],
        'missing': primary['missing'],
        'operations': primary['operations'],
        'evidence': primary['evidence'],
        'exclusion_reason': primary.get('exclusion_reason'),
        'status': status,
        'affected': affected,
        'recommendation': recommendation,
        'interpretations': [
            {'actual_sample': item['actual_sample'], 'via': item['via'],
             'eligible': item['eligible']}
            for item in outcomes
        ],
        'undetermined': primary['undetermined'],
        'merge_with': [],
    }


def _outcome(measurement, interpretation, case, events):
    actual = {'batch': interpretation['batch'], 'parent': interpretation['parent'],
              'aliquot': interpretation['aliquot']}
    operations = [_operation_row(measurement, actual, op, events)
                  for op in case['operations']]
    usable = {row['label'] for row in operations if row['usable']}
    missing = sorted(set(case['required']) - usable)
    evidence = list(interpretation['evidence'])
    for row in operations:
        if 'via' not in row:
            continue
        for item in row['evidence']:
            if item not in evidence:
                evidence.append(item)
    result = {
        'actual_sample': actual,
        'via': interpretation['via'],
        'operations': operations,
        'eligible': not missing,
        'missing': missing,
        'evidence': evidence,
        'undetermined': [],
    }
    if missing:
        result['exclusion_reason'] = _exclusion_reason(missing[0], operations)
        if any('晚于测量' in (row.get('reason') or '') for row in operations):
            result['undetermined'].append(
                f"测量 {measurement['at']} 相对实际分装的先后不能确定，纳入按登记时间核对")
    return result


def _operation_row(measurement, actual, op, events):
    row = {
        'label': op['label'],
        'at': op['at'],
        'batch': op['batch'],
        'container': op['container'],
        'before_split': bool(op.get('before_split')),
        'usable': False,
        'evidence': _event_evidence(op, events),
    }
    if op['batch'] != measurement['batch']:
        row['reason'] = f"属于批次 {op['batch']}"
        return row
    if op['container'] == actual['aliquot'] or op['container'] == measurement['sample']:
        row['via'] = '直接登记'
    elif actual['aliquot'] is None and op['container'] == actual['parent']:
        row['via'] = '直接登记'
    elif op['container'] == actual['parent'] and op.get('before_split'):
        row['via'] = '分装前继承'
    else:
        row['reason'] = f"仅跟随 {op['container']}"
        return row
    if not op['at'] < measurement['at']:
        row['reason'] = f"登记 {op['at']} 晚于测量 {measurement['at']}"
        return row
    row['usable'] = True
    return row


def _exclusion_reason(label, operations):
    candidates = [row for row in operations if row['label'] == label]
    for row in candidates:
        if '晚于测量' in (row.get('reason') or ''):
            return f"「{label}」登记 {row['at']} 晚于测量"
    if candidates:
        return f"「{label}」不可用：{candidates[0].get('reason', '原因未知')}"
    return f"缺少「{label}」登记"


def _resolve_events(facts, attribution):
    """把笔记中的交接事件定位到批次与实际分装物，并挂上同来源的补充说明。"""
    supplements = {}
    for fact in facts:
        if fact['kind'] == 'before_split':
            supplements.setdefault(fact['evidence']['source'], []).append(fact['evidence'])
    handovers = [fact for fact in facts if fact['kind'] in ('handover', 'no_handover')]
    mentions_by_record = {}
    for fact in handovers:
        mentions_by_record.setdefault(fact['evidence']['record_id'], set()).add(fact['mention'])
    events = []
    for fact in handovers:
        event = dict(fact)
        batches = attribution.batches_for(mentions_by_record[fact['evidence']['record_id']])
        if len(batches) == 1:
            batch = next(iter(batches))
            event['batch'] = batch
            resolved = attribution.resolve(batch, fact['mention'])
            event['resolved'] = resolved[0]['aliquot'] if resolved else None
        else:
            event['batch'] = None
            event['resolved'] = None
            event['undetermined'] = ('交接笔记未注明批次，且候选批次不唯一' if batches
                                     else '交接笔记中的名字无法对应任何批次')
        source = fact['evidence']['source']
        event['before_split'] = source in supplements
        event['supplements'] = supplements.get(source, [])
        events.append(event)
    return events


def _event_evidence(op, events):
    evidence = []
    for event in events:
        if event['kind'] != 'handover' or event.get('batch') != op['batch']:
            continue
        if event.get('label') != op['label']:
            continue
        if event.get('time') and _clock(op['at']) != event['time']:
            continue
        for item in [event['evidence'], *event.get('supplements', [])]:
            if item not in evidence:
                evidence.append(item)
    return evidence


def _mark_merge(measurements):
    groups = {}
    for measurement in measurements:
        actual = measurement['actual_sample']
        if actual:
            groups.setdefault((actual['batch'], actual['aliquot']), []).append(measurement)
    for members in groups.values():
        usable = [item['result'] for item in members if item['eligible']]
        for measurement in members:
            others = [result for result in usable if result != measurement['result']]
            measurement['merge_with'] = others if measurement['eligible'] else []


def _merge_groups(measurements):
    groups = {}
    for measurement in measurements:
        actual = measurement['actual_sample']
        if actual:
            key = (actual['batch'], actual['parent'], actual['aliquot'])
            groups.setdefault(key, []).append(measurement)
    rows = []
    for (batch, parent, aliquot), members in groups.items():
        rows.append({
            'actual_sample': {'batch': batch, 'parent': parent, 'aliquot': aliquot},
            'registered_names': sorted({item['registered_as'] for item in members}),
            'usable_together': [item['result'] for item in members if item['eligible']],
            'excluded': [
                {'result': item['result'],
                 'reason': item.get('exclusion_reason') or '不满足纳入条件'}
                for item in members if not item['eligible']
            ],
        })
    return rows


def _classify_facts(facts, events):
    """每条笔记事实相对分装的位置：分装前生效，或只跟随其中一管。"""
    by_key = {(event['evidence']['record_id'], event['kind'], event['mention']): event
              for event in events}
    rows = []
    for fact in facts:
        evidence = fact['evidence']
        row = {
            'record_id': evidence['record_id'],
            'source': evidence['source'],
            'revision': evidence['revision'],
            'kind': fact['kind'],
            'text': evidence['text'],
        }
        if fact['kind'] == 'split':
            row['classification'] = '分装关系登记'
            row['follows'] = f"批次 {fact['batch']} {fact['parent']} 的全部子样本"
        elif fact['kind'] in ('handover', 'no_handover'):
            event = by_key.get((evidence['record_id'], fact['kind'], fact['mention']))
            if fact['kind'] == 'handover' and event and event.get('before_split'):
                row['classification'] = '分装前事件'
                row['follows'] = '全部子样本'
            elif event and event.get('resolved'):
                suffix = '（未交接）' if fact['kind'] == 'no_handover' else ''
                row['classification'] = '分装后记录'
                row['follows'] = f"仅跟随 {event['resolved']}{suffix}"
            else:
                row['classification'] = '归属未定'
                row['follows'] = (event or {}).get('undetermined', '不能确定')
        elif fact['kind'] == 'instrument':
            row['classification'] = '仪器记录（相对分装先后未定）'
            row['follows'] = f"批次 {fact['batch']} {fact['sample']}（母样本）"
        elif fact['kind'] == 'before_split':
            row['classification'] = '补充说明'
            row['follows'] = '同来源的交接事件'
        else:
            row['classification'] = '更正或补充说明'
            row['follows'] = '相关记录'
        rows.append(row)
    return rows


def _conflicts(case, facts):
    """笔记与仪器时间对不上的地方：给出原文支持的解释和仍不能确定的点。"""
    explanations = [fact for fact in facts
                    if fact['kind'] == 'note'
                    and any('仪器时间可能早于签字' in claim for claim in fact['claims'])]
    conflicts = []
    for fact in facts:
        if fact['kind'] != 'instrument':
            continue
        related = [op for op in case['operations']
                   if op['batch'] == fact['batch'] and op['container'] == fact['sample']]
        if not related:
            conflicts.append({
                'subject': f"批次 {fact['batch']} 样本 {fact['sample']} 仪器记录 {fact['time']}",
                'status': '未对应',
                'explanation': None,
                'undetermined': '该仪器记录未对应任何已登记操作，与分装的先后关系不能确定',
                'evidence': [fact['evidence']],
            })
            continue
        for op in related:
            if _clock(op['at']) == fact['time']:
                continue
            conflicts.append({
                'subject': (f"批次 {fact['batch']} 样本 {fact['sample']} 仪器记录 {fact['time']} "
                            f"与登记「{op['label']}」{op['at']} 不一致"),
                'status': '时间不一致',
                'explanation': {'text': '仪器时间可能早于签字',
                                'evidence': explanations[0]['evidence']} if explanations else None,
                'undetermined': '分装的具体时点未记录，先后关系按登记时间核对',
                'evidence': [fact['evidence']],
            })
    return conflicts


def _undetermined(case, facts, events, measurements):
    points = []
    if any(fact.get('time') and 'T' not in str(fact['time']) for fact in facts):
        points.append('笔记中的钟点未注明日期，与登记时间对照时按同日处理')
    timing = [fact for fact in facts if fact['kind'] == 'note'
              and any(claim.startswith('分装在') for claim in fact['claims'])]
    if timing:
        claim = next(claim for claim in timing[0]['claims'] if claim.startswith('分装在'))
        points.append(f"分装的具体时点未记录（{timing[0]['evidence']['record_id']}：{claim}）")
    for op in case['operations']:
        if not _event_evidence(op, events):
            points.append(f"操作「{op['label']}」{op['at']} 未找到对应笔记原文")
    for measurement in measurements:
        for point in measurement['undetermined']:
            if point not in points:
                points.append(point)
    return points
