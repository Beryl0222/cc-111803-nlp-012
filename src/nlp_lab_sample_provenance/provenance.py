"""样本归属：登记名、别名与实际分装物的对应，以及多解释处理。

样本号在每个批次内唯一，跨批次可重复，因此归属一律按批次核对。
别名（如「第一管」「剩下那管」）按分装顺序解释；登记顺序与笔记顺序
不一致时，两种顺序都作为合理解释保留，由核对层判断归属是否受影响。
"""

_ALIAS_FIRST = '第一管'
_ALIAS_REST = '剩下那管'
ALIASES = (_ALIAS_FIRST, _ALIAS_REST)


class Attribution:
    """按批次解析样本名，返回全部合理解释及原文依据。"""

    def __init__(self, samples, facts=None):
        self.parent_of = {}
        self.children_of = {}
        for row in samples:
            key = (row['batch'], row['sample'])
            self.children_of.setdefault(key, [])
            for child in row['children']:
                child_key = (row['batch'], child)
                if child_key in self.parent_of:
                    raise ValueError(f'分装编号重复：{child_key}')
                self.parent_of[child_key] = row['sample']
                self.children_of[key].append(child)
        self._split_facts = {}
        for fact in facts or []:
            if fact['kind'] == 'split':
                self._split_facts.setdefault((fact['batch'], fact['parent']), []).append(fact)

    def split_evidence(self, batch, parent):
        return [fact['evidence'] for fact in self._split_facts.get((batch, parent), [])]

    def _orderings(self, batch, parent):
        """分装顺序的全部解释：登记顺序与笔记顺序，按顺序去重并合并依据。"""
        orderings = {}
        registered = self.children_of.get((batch, parent))
        if registered:
            orderings.setdefault(tuple(registered), [])
        for fact in self._split_facts.get((batch, parent), []):
            orderings.setdefault(tuple(fact['children']), []).append(fact['evidence'])
        return [(list(children), evidence) for children, evidence in orderings.items()]

    def resolve(self, batch, name):
        """名字 → 实际分装物的全部合理解释；解释为空表示不能确定。"""
        if (batch, name) in self.parent_of:
            parent = self.parent_of[(batch, name)]
            return [{'batch': batch, 'parent': parent, 'aliquot': name, 'via': '登记名',
                     'evidence': self.split_evidence(batch, parent)}]
        if (batch, name) in self.children_of:
            return [{'batch': batch, 'parent': name, 'aliquot': None, 'via': '母样本',
                     'evidence': self.split_evidence(batch, name)}]
        if name in ALIASES:
            return self._resolve_alias(batch, name)
        return []

    def _resolve_alias(self, batch, alias):
        interpretations = []
        for (candidate, parent) in self.children_of:
            if candidate != batch:
                continue
            for children, evidence in self._orderings(batch, parent):
                targets = children[:1] if alias == _ALIAS_FIRST else children[1:]
                for target in targets:
                    interpretations.append({
                        'batch': batch, 'parent': parent, 'aliquot': target,
                        'via': f'别名「{alias}」', 'evidence': evidence,
                    })
        return interpretations

    def batches_for(self, mentions):
        """全部提及都能解释的候选批次（用于未注明批次的笔记）。"""
        candidates = None
        for mention in mentions:
            if mention in ALIASES:
                possible = {batch for (batch, _parent) in self.children_of
                            if self._resolve_alias(batch, mention)}
            else:
                possible = {batch for (batch, child) in self.parent_of if child == mention}
                possible |= {batch for (batch, parent) in self.children_of if parent == mention}
            candidates = possible if candidates is None else candidates & possible
        return candidates or set()
