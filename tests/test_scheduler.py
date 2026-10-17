"""Scheduling must remain UTC-based and safe to inspect without publishing."""
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import schedule


ROOT = Path(__file__).resolve().parents[1]


def test_import_and_registration_do_not_start_services_or_modify_global_scheduler(tmp_path):
    code = """
import logging
from pathlib import Path
import schedule
import sys
import types

def unexpected_import(name):
    raise AssertionError('Generator imported before a job runs: ' + name)

for name in ('video_gen', 'battle_gen', 'drop_gen', 'tournament_gen'):
    stub = types.ModuleType(name)
    stub.__getattr__ = unexpected_import
    sys.modules[name] = stub
original_stdout = sys.stdout
original_handlers = list(logging.getLogger().handlers)
import scheduler
runner = scheduler.configure_schedule(scheduler.ScheduleConfig())
assert len(runner.jobs) == 5
assert not schedule.jobs
assert sys.stdout is original_stdout
assert logging.getLogger().handlers == original_handlers
assert not list(Path.cwd().iterdir())
"""
    result = subprocess.run(
        [sys.executable, '-c', code], cwd=tmp_path,
        env={**os.environ, 'PYTHONPATH': str(ROOT)},
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('host_offset', [5, -7])
def test_jobs_keep_their_utc_times_on_non_utc_hosts(monkeypatch, host_offset):
    import scheduler

    host_timezone = timezone(timedelta(hours=host_offset))

    class HostDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            moment = cls(2026, 10, 17, 22, 30, tzinfo=timezone.utc)
            if tz is not None:
                return moment.astimezone(tz)
            return moment.astimezone(host_timezone).replace(tzinfo=None)

        def astimezone(self, tz=None):
            return super().astimezone(tz if tz is not None else host_timezone)

    monkeypatch.setattr(schedule.datetime, 'datetime', HostDateTime)
    runner = scheduler.configure_schedule(scheduler.ScheduleConfig())
    expected = [(18, 5, 15), (18, 11, 15), (18, 17, 15),
                (21, 6, 15), (18, 14, 15)]
    for job, (day, hour, minute) in zip(runner.jobs, expected):
        next_utc = job.next_run.replace(tzinfo=host_timezone).astimezone(timezone.utc)
        assert next_utc == datetime(2026, 10, day, hour, minute, tzinfo=timezone.utc)
        assert str(job.at_time_zone) == 'UTC'
    assert [job.interval for job in runner.jobs] == [1, 1, 1, 4, 1]


def test_environment_overrides_and_kazakhstan_midnight_display(monkeypatch):
    import scheduler

    for name in ('POST_TIMES', 'BATTLE_SLOT', 'TOURNAMENT_POST_TIME', 'DROP_POST_TIME'):
        monkeypatch.delenv(name, raising=False)
    assert scheduler.ScheduleConfig.from_environment() == scheduler.ScheduleConfig()
    monkeypatch.setenv('POST_TIMES', ' 23:45, ,07:15 ')
    monkeypatch.setenv('BATTLE_SLOT', '1')
    monkeypatch.setenv('TOURNAMENT_POST_TIME', '00:15')
    monkeypatch.setenv('DROP_POST_TIME', '16:30')
    config = scheduler.ScheduleConfig.from_environment()
    assert config == scheduler.ScheduleConfig(('23:45', '07:15'), 1, '00:15', '16:30')
    assert scheduler._kz_time(config.post_times[0]) == '04:45'


def test_daily_slots_dispatch_two_races_and_one_battle(monkeypatch):
    import scheduler

    race, battle, notify = Mock(), Mock(), Mock()
    monkeypatch.setitem(sys.modules, 'video_gen',
                        SimpleNamespace(generate_video=race, send_telegram=notify))
    monkeypatch.setitem(sys.modules, 'battle_gen',
                        SimpleNamespace(generate_battle_video=battle))
    runner = scheduler.configure_schedule(scheduler.ScheduleConfig())
    for job in runner.jobs[:3]:
        job.job_func()
    assert race.call_count == 2
    battle.assert_called_once_with()
    assert notify.call_count == 3
