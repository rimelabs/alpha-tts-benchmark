"""Check the specification freeze and exact corpus allocation; no network calls."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def rows(path: str) -> dict:
    data = [json.loads(line) for line in (ROOT / path).read_text().splitlines() if line]
    result = {row['id']: row for row in data}
    if len(result) != len(data):
        raise ValueError(f'Duplicate IDs: {path}')
    return result


def pinned_paths(root: Path) -> set[str]:
    paths = {'.gitignore', 'README.md', 'PROTOCOL.md', 'pyproject.toml', 'uv.lock'}
    for directory, pattern in (
        ('configs', '*.json'), ('corpus', '*.py'), ('data', '*.jsonl'),
        ('docs', '*.md'), ('scripts', '*.py'), ('tests', '*.py'),
    ):
        paths.update(str(path.relative_to(root)) for path in (root / directory).rglob(pattern))
    paths.discard('configs/freeze_manifest.json')
    return paths


def check() -> None:
    freeze = json.loads((ROOT / 'configs/freeze_manifest.json').read_text())
    if set(freeze['sha256']) != pinned_paths(ROOT):
        raise ValueError('Freeze manifest does not cover the specification files exactly')
    for name, expected in freeze['sha256'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Frozen file changed: {name}')
    design = json.loads((ROOT / 'configs/run_design.json').read_text())
    if freeze.get('freeze_kind') != 'specification' or design.get('freeze_kind') != 'specification':
        raise ValueError('Expected a specification freeze')
    tasks = json.loads((ROOT / 'configs/listener_tasks.json').read_text())
    if not (freeze['freeze_date'] == design['freeze_date'] == tasks['freeze_date']):
        raise ValueError('Freeze dates disagree')
    if not (freeze['protocol_version'] == design['protocol_version'] == tasks['task_version']):
        raise ValueError('Protocol and listener-task versions disagree')
    jobs = design['jobs']
    if len(jobs) != 17 or len({job['id'] for job in jobs}) != 17:
        raise ValueError('Expected 17 distinct evaluations')
    total = 0
    for job in jobs:
        data = rows(job['corpus'])
        multiplier = len(job['providers']) if job['benchmark'] == 'alphabench' else 1
        expected = len(data) * job['ratings_per_item'] * multiplier
        if len(data) != job['items'] or expected != job['judgments']:
            raise ValueError(f"Invalid allocation: {job['id']}")
        total += expected
    if total != design['total_judgments'] or total != 32450:
        raise ValueError('Expected 32,450 judgments')
    for benchmark in ('supportbench', 'contentbench'):
        full = rows(f'data/{benchmark}.jsonl')
        tranche = rows(f'data/tranche_{benchmark}.jsonl')
        continuation = rows(f'data/continuation_{benchmark}.jsonl')
        if tranche.keys() & continuation.keys() or full != tranche | continuation:
            raise ValueError(f'Invalid exact partition: {benchmark}')
    if rows('data/alphabench.jsonl').keys() & rows('data/pilot_alphabench_icc.jsonl').keys():
        raise ValueError('Alpha pilot/main IDs collide')
    if design['status'] != 'frozen' or design['audio']['mode'] != 'level-matched':
        raise ValueError('Expected frozen level-matched audio design')
    if design['audio'].get('target_lufs') != -23 or design['audio'].get('true_peak_db') != -1:
        raise ValueError('Expected -23 LUFS target and -1 dBTP ceiling')
    if design['audio']['podonos_loudness_normalization']:
        raise ValueError('Podonos normalization must be off')
    print('Freeze verified: 17 evaluations, 32,450 judgments; exact corpus partitions and file hashes match.')


if __name__ == '__main__':
    check()
