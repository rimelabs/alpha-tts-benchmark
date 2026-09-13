from __future__ import annotations

import contextlib
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import check_frozen_run


class FreezeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        manifest = json.loads((ROOT / 'configs/freeze_manifest.json').read_text())
        for name in [*manifest['sha256'], 'configs/freeze_manifest.json']:
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, destination)

    def check(self) -> None:
        with patch.object(check_frozen_run, 'ROOT', self.root), contextlib.redirect_stdout(io.StringIO()):
            check_frozen_run.check()

    def test_complete_snapshot_passes(self) -> None:
        self.check()

    def test_modified_corpus_is_rejected(self) -> None:
        with (self.root / 'data/supportbench.jsonl').open('a') as stream:
            stream.write('\n')
        with self.assertRaisesRegex(ValueError, 'Frozen file changed'):
            self.check()

    def test_unpinned_analysis_script_is_rejected(self) -> None:
        (self.root / 'scripts/extra_analysis.py').write_text('pass\n')
        with self.assertRaisesRegex(ValueError, 'cover the specification files exactly'):
            self.check()

    def test_rehashed_inconsistent_freeze_date_is_rejected(self) -> None:
        path = self.root / 'configs/run_design.json'
        design = json.loads(path.read_text())
        design['freeze_date'] = '2000-01-01'
        path.write_text(json.dumps(design))
        manifest_path = self.root / 'configs/freeze_manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['sha256']['configs/run_design.json'] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'Freeze dates disagree'):
            self.check()


if __name__ == '__main__':
    unittest.main()
