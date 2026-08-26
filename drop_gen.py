"""
"Marble Drop" video generator — a third mode alongside the maze race
(video_gen.py) and the battle royale (battle_gen.py), built on the same
code-only engine (race_sim.py). Zero-AI, zero-maze: colorful squares spawn
at the top of a long vertical Plinko-style track and pure pymunk gravity +
collisions with static pegs and spinning blades decide the outcome, first
to cross the finish line wins. Independent schedule/cron from the other
three video types (see scheduler.py / .github/workflows/drop.yml); shares
the YouTube channel, OAuth credentials, Openverse music, SFX synthesis and
Telegram notify helpers with video_gen.py.
"""
import os
import random
import logging
import traceback

import numpy as np
from moviepy import AudioFileClip, AudioArrayClip, CompositeAudioClip, concatenate_audioclips
from dotenv import load_dotenv

from race_sim import (
    simulate_drop, build_drop_clip, build_sfx_array, generate_thumbnail,
    build_duck_envelope, race_bump_times, SR as SFX_SR,
)
from video_gen import (
    base_dir, send_telegram, retry_with_backoff, ensure_directories_exist,
    get_recent_matchups, pick_background_music, upload_to_youtube, cleanup_temp_files,
    MAX_RETRIES, RETRY_DELAY, YOUTUBE_CATEGORY_ID,
    YOUTUBE_PRIVACY_STATUS, YOUTUBE_MADE_FOR_KIDS, VIDEO_CODEC, AUDIO_CODEC,
    VIDEO_PRESET, MUSIC_VOLUME, SFX_VOLUME, AVOID_REPEAT_LOOKBACK, AVOID_REPEAT_MAX_ATTEMPTS,
)

load_dotenv()

DROP_WIDTH = int(os.getenv('DROP_VIDEO_WIDTH', '1080'))
DROP_HEIGHT = int(os.getenv('DROP_VIDEO_HEIGHT', '1920'))
DROP_FPS = int(os.getenv('DROP_VIDEO_FPS', '60'))
DROP_MAX_SECONDS = int(os.getenv('DROP_MAX_SECONDS', '22'))
DROP_MIN_SECONDS = int(os.getenv('DROP_MIN_SECONDS', '8'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(base_dir, 'drop_debug.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DROP_TITLE_TEMPLATES = [
    "{names} — Marble Drop! Who Wins?",
    "{n}-Way Marble Drop: {names}",
    "Gravity Decides: {names}",
    "{names} — Plinko Race #shorts",
    "Can {winner} Win the Drop?",
]

DROP_DESCRIPTION_TEMPLATES = [
    "{names} drop down a random Plinko-style track!\n"
    "Winner: {winner} 🏆\n\n"
    "Fully generated physics, zero footage, zero copyright risk. New track every upload.",

    "🟦🎯 {names} just tumbled down a totally random peg track!\n\n"
    "🏆 Winner: {winner}\n\n"
    "No script, no real footage — just pure gravity and bouncy physics. New track every day!",

    "Gravity, pegs, spinning blades... only ONE square makes it down first. 💥\n\n"
    "{names}\n"
    "🏆 {winner} takes the win!\n\n"
    "Every track, every racer, every outcome — 100% randomly generated.",

    "🎲 Random track. Zero controls. One winner.\n\n"
    "{names} → {winner} wins!\n\n"
    "New chaos every single upload — who do you think should've won?",
]

DROP_HASHTAG_POOL = [
    "#shorts", "#marbledrop", "#plinko", "#satisfying", "#physics",
    "#fyp", "#viral", "#whowins", "#simulation", "#gravity",
]


def _pick_drop_tags(count=6):
    return ' '.join(random.sample(DROP_HASHTAG_POOL, min(count, len(DROP_HASHTAG_POOL))))


def build_drop_title_and_description(racer_names, winner_name):
    names_joined = " vs ".join(racer_names)
    template = random.choice(DROP_TITLE_TEMPLATES)
    title = template.format(names=names_joined, n=len(racer_names), winner=winner_name)[:95]

    racer_tags = ' '.join(f"#{name.lower()}" for name in racer_names[:3])
    hashtags = f"{racer_tags} {_pick_drop_tags()}"
    body = random.choice(DROP_DESCRIPTION_TEMPLATES).format(names=names_joined, winner=winner_name)
    description = f"{body}\n\n{hashtags}"
    tags = list(racer_names) + ["marble drop", "plinko", "physics simulation", "shorts"]
    return title, description, tags


def generate_drop_video(skip_upload: bool = False, n_racers: int = None):
    try:
        logger.info("🎯 Marble Drop видео құру процессі басталды")

        ensure_directories_exist()
        cleanup_temp_files()

        recent_matchups = get_recent_matchups(AVOID_REPEAT_LOOKBACK)

        seed = random.randint(1, 2**31 - 1)
        race = simulate_drop(
            w=DROP_WIDTH, h=DROP_HEIGHT, seed=seed, fps=DROP_FPS,
            max_seconds=DROP_MAX_SECONDS, min_seconds=DROP_MIN_SECONDS,
            n_racers=n_racers,
        )
        racer_names = [r["name"] for r in race["racers"]]

        attempts = 1
        while frozenset(racer_names) in recent_matchups and attempts < AVOID_REPEAT_MAX_ATTEMPTS:
            seed = random.randint(1, 2**31 - 1)
            race = simulate_drop(
                w=DROP_WIDTH, h=DROP_HEIGHT, seed=seed, fps=DROP_FPS,
                max_seconds=DROP_MAX_SECONDS, min_seconds=DROP_MIN_SECONDS,
                n_racers=n_racers,
            )
            racer_names = [r["name"] for r in race["racers"]]
            attempts += 1
        if attempts > 1:
            logger.info(f"🔁 Қайталанатын құрам аттап өтілді ({attempts} әрекет)")

        winner_name = race["winner_name"]
        logger.info(f"🎯 Drop ({race['n_racers']}): {' vs '.join(racer_names)} — жеңімпаз: {winner_name}")

        video_title, video_description, video_tags = build_drop_title_and_description(
            racer_names, winner_name
        )
        logger.info(f"🏷️ Тақырып: {video_title}")

        thumbnail_path = os.path.join(base_dir, "drop_thumbnail.jpg")
        try:
            generate_thumbnail(race, thumbnail_path, caption="GRAVITY DECIDES!",
                                banner_color=(60, 170, 230), badge_text=f"{race['n_racers']}-WAY MARBLE DROP")
            logger.info("✓ Custom thumbnail дайын")
        except Exception as e:
            logger.warning(f"⚠️ Thumbnail генерациясы сәтсіз: {e}")
            thumbnail_path = None

        drop_clip = None
        music_clip = None
        sfx_clip = None
        final_video = None

        try:
            drop_clip = build_drop_clip(race)
            duration = drop_clip.duration

            sfx_array, sfx_sr = build_sfx_array(race)
            sfx_clip = AudioArrayClip(sfx_array, fps=sfx_sr).subclipped(0, duration)
            audio_tracks = [sfx_clip.with_volume_scaled(SFX_VOLUME)]

            music_path, music_attribution = pick_background_music(duration)

            if music_path:
                music_clip = AudioFileClip(music_path)
                if music_clip.duration < duration:
                    loops_needed = int(duration / music_clip.duration) + 1
                    music_clip = concatenate_audioclips([music_clip] * loops_needed)
                music_clip = music_clip.subclipped(0, duration).with_volume_scaled(MUSIC_VOLUME)

                try:
                    music_array = music_clip.to_soundarray(fps=SFX_SR)
                    if music_array.ndim == 1:
                        music_array = np.stack([music_array, music_array], axis=1)
                    envelope = build_duck_envelope(len(music_array), SFX_SR, race_bump_times(race))
                    music_clip = AudioArrayClip(music_array * envelope[:, None], fps=SFX_SR)
                except Exception as e:
                    logger.warning(f"⚠️ Ducking қатесі, ducking-сіз жалғастырылады: {e}")

                audio_tracks.append(music_clip)
                if music_attribution:
                    video_description += f"\n\n{music_attribution}"
                logger.info(f"🎵 Музыка таңдалды: {os.path.basename(music_path)}")
            else:
                logger.warning("⚠️ Фон музыкасы табылмады, тек SFX қолданылады")

            final_audio = CompositeAudioClip(audio_tracks)
            final_video = drop_clip.with_audio(final_audio)

            final_output = os.path.join(base_dir, "final_drop.mp4")
            logger.info(f"\n⏳ Видео құрылуда ({VIDEO_CODEC}, {DROP_FPS}fps, {duration:.1f}с)...")

            try:
                final_video.write_videofile(
                    final_output,
                    codec=VIDEO_CODEC,
                    audio_codec=AUDIO_CODEC,
                    fps=DROP_FPS,
                    preset=VIDEO_PRESET,
                    logger=None
                )
            except Exception as write_error:
                logger.warning(f"⚠️ Видео жазу қатесі: {write_error}")
                logger.info("   Резервтік кодек қолданылуда...")
                final_video.write_videofile(
                    final_output,
                    codec="mpeg4",
                    audio_codec="libmp3lame",
                    fps=DROP_FPS,
                    preset='ultrafast'
                )

            logger.info(f"✓ Видео дайын: {final_output}")

            if not skip_upload:
                video_id = retry_with_backoff(lambda: upload_to_youtube(final_output, video_title, video_description, video_tags, thumbnail_path))
                video_url = f"https://youtube.com/shorts/{video_id}"
                send_telegram(
                    f"✅ <b>Жаңа Marble Drop видео жүктелді!</b>\n"
                    f"🎯 <b>{' vs '.join(racer_names)}</b>\n"
                    f"🏆 Жеңімпаз: {winner_name}\n"
                    f"🔗 {video_url}"
                )
            else:
                logger.info("✓ Видео сақталды (жүктеу өтіп кетті)")

        finally:
            try:
                if drop_clip:
                    drop_clip.close()
                if music_clip:
                    music_clip.close()
                if sfx_clip:
                    sfx_clip.close()
                if final_video:
                    final_video.close()
                logger.info("✓ Ресурстар босатылды")
            except Exception:
                pass

    except Exception as e:
        logger.error(f"❌ Қате: {e}")
        logger.debug(traceback.format_exc())
        send_telegram(f"❌ <b>Marble Drop видео жасауда қате шықты!</b>\n<code>{str(e)[:300]}</code>")
        raise


if __name__ == "__main__":
    try:
        generate_drop_video()
    except Exception as e:
        logger.error(f"Программа сәтсіз аяқталды: {e}")
