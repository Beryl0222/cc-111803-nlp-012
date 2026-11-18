class ContainerRegistry:
    def __init__(self, stocks):
        self.parent = {}
        for row in stocks:
            for child in row['children']:
                key = row['batch'], child
                if key in self.parent:
                    raise ValueError(f'分装编号重复：{key}')
                self.parent[key] = row['sample']

    def identify(self, batch, sample):
        if (batch, sample) not in self.parent:
            raise ValueError('样本未登记在该批次')
        return self.parent[batch, sample]


class TransferHistory:
    def __init__(self, registry, operations):
        self.registry = registry
        self.operations = operations

    def before_measurement(self, result):
        batch, sample = result['batch'], result['sample']
        parent = self.registry.identify(batch, sample)
        return {op['label'] for op in self.operations if op['batch'] == batch and op['at'] < result['at']
                and (op['container'] == sample or (op['container'] == parent and op['before_split']))}


class AnalysisIntake:
    def __init__(self, history, signed):
        self.history = history
        self.signed = {item['result']: item for item in signed}

    def inspect(self, result, required):
        labels = self.history.before_measurement(result)
        missing = set(required) - labels
        return {'result': result['id'], 'missing': sorted(missing), 'eligible': not missing,
                'signed_inclusion': self.signed.get(result['id'])}


def assess(case, registry):
    histories = TransferHistory(ContainerRegistry(registry['samples']), case['operations'])
    intake = AnalysisIntake(histories, registry['signed_inclusions'])
    return [intake.inspect(result, case['required']) for result in case['measurements']]
