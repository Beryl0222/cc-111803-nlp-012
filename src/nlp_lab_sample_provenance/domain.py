import json
from pathlib import Path

def load_facts(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def summarize(facts):
    return [row['result'] for row in facts['signed_inclusions'] if row['analysis'] == 'AN-1']
