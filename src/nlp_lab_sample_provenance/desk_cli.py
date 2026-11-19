import argparse
import json
from pathlib import Path

from .desk import assess, review
from .notes import flatten_facts, parse_records


def load_case(case_path, registry_path):
    case = json.loads(case_path.read_text(encoding='utf-8'))
    registry = json.loads(registry_path.read_text(encoding='utf-8'))
    return assess(case, registry)


def load_review(case_path, registry_path, notes_path=None):
    case = json.loads(case_path.read_text(encoding='utf-8'))
    registry = json.loads(registry_path.read_text(encoding='utf-8'))
    facts = []
    if notes_path is not None:
        records = json.loads(notes_path.read_text(encoding='utf-8'))
        facts = flatten_facts(parse_records(records))
    return review(case, registry, facts)


def main():
    parser = argparse.ArgumentParser(description='核对合成样本登记和分析纳入范围')
    parser.add_argument('--case', type=Path, default=Path('fixtures/work.json'))
    parser.add_argument('--registry', type=Path, default=Path('fixtures/business.json'))
    parser.add_argument('--notes', type=Path, default=Path('fixtures/records.json'))
    args = parser.parse_args()
    try:
        result = load_review(args.case, args.registry, args.notes)
    except (OSError, KeyError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
