"""A legitimate Battle survivor must not inflate raw physics timeout counts."""
import json
from pathlib import Path
import runpy
import sys

import race_sim


def test_audit_distinguishes_last_standing_and_reports_true_timeout(monkeypatch, tmp_path, capsys):
    def simulate(*args, n_racers, **kwargs):
        reason = 'last_standing' if n_racers == 2 else 'timeout' if n_racers == 3 else 'finish'
        return dict(
            racer_radius=20, finale_start=1,
            frames=[dict(pos=[(i * 40, 100, 0) for i in range(n_racers)],
                         active=[True] + [False] * (n_racers - 1))],
            full_ranking=list(range(n_racers)), result_reason=reason,
            winner_finished=reason == 'finish', winner_idx=0,
            finish_frame_flags={0: [(0, 0, 100)]} if reason == 'finish' else {},
            elim_frame_flags={0: [(1, 40, 100)]} if reason == 'last_standing' else {},
        )

    output = tmp_path / 'audit.json'
    monkeypatch.setattr(race_sim, 'simulate_battle', simulate)
    monkeypatch.setattr(sys, 'argv', ['audit_physics.py', '--mode', 'battle',
                                    '--seeds', '1', '--output', str(output)])
    runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts' / 'audit_physics.py'))
    rows = json.loads(output.read_text())
    assert rows[0]['result_reason'] == 'last_standing'
    assert not rows[0]['timeout']
    assert rows[1]['timeout']
    assert sum(row['timeout'] for row in rows) == 1
    summary = capsys.readouterr().out
    assert 'timeouts 1 last_standing 1' in summary
