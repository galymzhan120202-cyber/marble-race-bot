"""Run the publishing schedule in UTC, independent of the host timezone."""
import logging
import os
import sys
import time
from dataclasses import dataclass

import schedule
from dotenv import load_dotenv


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScheduleConfig:
    post_times: tuple[str, ...] = ('05:15', '11:15', '17:15')
    battle_slot: int = 2
    tournament_time: str = '06:15'
    drop_time: str = '14:15'

    @classmethod
    def from_environment(cls):
        post_times = tuple(t.strip() for t in os.getenv(
            'POST_TIMES', '05:15,11:15,17:15').split(',') if t.strip())
        return cls(
            post_times=post_times,
            battle_slot=int(os.getenv('BATTLE_SLOT', str(min(2, len(post_times))))),
            tournament_time=os.getenv('TOURNAMENT_POST_TIME', '06:15'),
            drop_time=os.getenv('DROP_POST_TIME', '14:15'),
        )


def _kz_time(utc_time):
    hour, minute = map(int, utc_time.split(':'))
    return f'{(hour + 5) % 24:02d}:{minute:02d}'


def make_job(slot_num, config):
    is_battle = slot_num == config.battle_slot

    def job():
        from video_gen import generate_video, send_telegram

        kind = "Battle Royale" if is_battle else "Maze Race"
        logger.info(f"⏰ {slot_num}-жүктеу басталды ({kind})...")
        send_telegram(f"⏰ <b>{kind} {slot_num}/{len(config.post_times)} жүктеу басталды</b>")
        try:
            if is_battle:
                from battle_gen import generate_battle_video
                generate_battle_video()
            else:
                generate_video()
            logger.info(f"✅ {slot_num}-жүктеу сәтті аяқталды")
        except Exception as e:
            logger.error(f"❌ {slot_num}-жүктеу сәтсіз: {e}")

    return job


def tournament_job():
    from video_gen import send_telegram
    from tournament_gen import generate_tournament_video

    logger.info("⏰ Tournament жүктеу басталды...")
    send_telegram("⏰ <b>Maze Race Tournament жүктеу басталды</b>")
    try:
        generate_tournament_video()
        logger.info("✅ Tournament жүктеу сәтті аяқталды")
    except Exception as e:
        logger.error(f"❌ Tournament жүктеу сәтсіз: {e}")


def drop_job():
    from video_gen import send_telegram
    from drop_gen import generate_drop_video

    logger.info("⏰ Marble Drop жүктеу басталды...")
    send_telegram("⏰ <b>Marble Drop жүктеу басталды</b>")
    try:
        generate_drop_video()
        logger.info("✅ Marble Drop жүктеу сәтті аяқталды")
    except Exception as e:
        logger.error(f"❌ Marble Drop жүктеу сәтсіз: {e}")


def configure_schedule(config):
    """Register jobs without executing them or contacting publishing services."""
    runner = schedule.Scheduler()
    for i, utc_time in enumerate(config.post_times, start=1):
        runner.every().day.at(utc_time, 'UTC').do(make_job(i, config))
        logger.info(f"  ✓ {i}-жүктеу: {utc_time} UTC ({_kz_time(utc_time)} KZ)")

    # The four-day interval starts with this process, independently of Shorts.
    # GitHub Actions approximates this with fixed days of the month instead.
    runner.every(4).days.at(config.tournament_time, 'UTC').do(tournament_job)
    logger.info(f"  ✓ Tournament: әр 4 күн сайын {config.tournament_time} UTC "
                f"({_kz_time(config.tournament_time)} KZ)")
    runner.every().day.at(config.drop_time, 'UTC').do(drop_job)
    logger.info(f"  ✓ Marble Drop: күнде {config.drop_time} UTC "
                f"({_kz_time(config.drop_time)} KZ)")
    return runner


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.FileHandler('scheduler.log', encoding='utf-8'),
                  logging.StreamHandler()],
    )
    config = ScheduleConfig.from_environment()
    runner = configure_schedule(config)
    from video_gen import send_telegram

    logger.info(f"🚀 Maze Race Scheduler іске қосылды — күнде {len(config.post_times)} Shorts + "
                "күнде 1 Marble Drop + әр 4 күн Tournament")
    logger.info("   Тоқтату үшін Ctrl+C")
    send_telegram(
        f"🚀 <b>Maze Race Scheduler іске қосылды</b>\n"
        f"📅 Shorts: күнде <b>{len(config.post_times)} видео</b>\n"
        f"🕐 Уақыттары (KZ): <b>{' / '.join(map(_kz_time, config.post_times))}</b>\n"
        f"🎯 Marble Drop: күнде, {_kz_time(config.drop_time)} (KZ)\n"
        f"🏆 Tournament: әр <b>4 күн</b>, {_kz_time(config.tournament_time)} (KZ)"
    )
    while True:
        runner.run_pending()
        time.sleep(30)


if __name__ == '__main__':
    main()
