import os
import sys
import io
import schedule
import time
import logging
from dotenv import load_dotenv

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
load_dotenv()

POST_TIMES = [
    t.strip()
    for t in os.getenv('POST_TIMES', '05:15,11:15,17:15').split(',')
    if t.strip()
]

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scheduler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

from video_gen import generate_video, send_telegram
from tournament_gen import generate_tournament_video

TOURNAMENT_TIME = os.getenv('TOURNAMENT_POST_TIME', '08:15')

def make_job(slot_num):
    def job():
        logger.info(f"⏰ {slot_num}-жүктеу басталды...")
        send_telegram(f"⏰ <b>Maze Race {slot_num}/{len(POST_TIMES)} жүктеу басталды</b>")
        try:
            generate_video()
            logger.info(f"✅ {slot_num}-жүктеу сәтті аяқталды")
        except Exception as e:
            logger.error(f"❌ {slot_num}-жүктеу сәтсіз: {e}")
    return job

def tournament_job():
    logger.info("⏰ Tournament жүктеу басталды...")
    send_telegram("⏰ <b>Maze Race Tournament жүктеу басталды</b>")
    try:
        generate_tournament_video()
        logger.info("✅ Tournament жүктеу сәтті аяқталды")
    except Exception as e:
        logger.error(f"❌ Tournament жүктеу сәтсіз: {e}")

for i, t in enumerate(POST_TIMES, start=1):
    schedule.every().day.at(t).do(make_job(i))
    logger.info(f"  ✓ {i}-жүктеу: {t} UTC ({int(t.split(':')[0])+5:02d}:{t.split(':')[1]} KZ)")

# Tournament (long-form, 16-racer bracket) is completely independent of the
# Shorts POST_TIMES cadence above — its own schedule.every(4).days job, so a
# Shorts-schedule change never accidentally shifts it. Note: the 4-day
# interval is counted from whenever this process starts (the `schedule`
# library has no calendar anchor), so a long-running process is what keeps
# it actually every 4 days — see SETUP.md for the GitHub Actions equivalent.
schedule.every(4).days.at(TOURNAMENT_TIME).do(tournament_job)
logger.info(f"  ✓ Tournament: әр 4 күн сайын {TOURNAMENT_TIME} UTC "
            f"({int(TOURNAMENT_TIME.split(':')[0]) + 5:02d}:{TOURNAMENT_TIME.split(':')[1]} KZ)")

kz_times = [f"{int(t.split(':')[0])+5:02d}:{t.split(':')[1]}" for t in POST_TIMES]
kz_tournament = f"{int(TOURNAMENT_TIME.split(':')[0]) + 5:02d}:{TOURNAMENT_TIME.split(':')[1]}"
logger.info(f"🚀 Maze Race Scheduler іске қосылды — күнде {len(POST_TIMES)} Shorts + әр 4 күн Tournament")
logger.info("   Тоқтату үшін Ctrl+C")
send_telegram(
    f"🚀 <b>Maze Race Scheduler іске қосылды</b>\n"
    f"📅 Shorts: күнде <b>{len(POST_TIMES)} видео</b>\n"
    f"🕐 Уақыттары (KZ): <b>{' / '.join(kz_times)}</b>\n"
    f"🏆 Tournament: әр <b>4 күн</b>, {kz_tournament} (KZ)"
)

while True:
    schedule.run_pending()
    time.sleep(30)
