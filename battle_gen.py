"""
"Battle Royale" video generator — a second mode alongside the Shorts maze
race (video_gen.py), built on the same code-only maze engine (race_sim.py).
Racers spawn in a closed arena instead of racing to a finish line: a
shrinking safe zone forces them together, scattered weapon pickups let an
armed racer eliminate an unarmed one on collision, and the last racer
standing wins. Independent schedule/cron from both the Shorts and the
Tournament (see scheduler.py / .github/workflows/battle.yml); shares the
YouTube channel, OAuth credentials, Openverse music, SFX synthesis and
Telegram notify helpers with video_gen.py.
"""
import os
import random
import logging
import traceback

import numpy as np
from moviepy import AudioFileClip, AudioArrayClip, CompositeAudioClip, concatenate_videoclips, concatenate_audioclips
from dotenv import load_dotenv

from race_sim import (
    simulate_battle, build_battle_clip, build_sfx_array, generate_thumbnail,
    build_duck_envelope, race_bump_times, SR as SFX_SR,
    build_battle_cold_open_clip, build_cold_open_sfx,
)
from video_gen import (
    base_dir, send_telegram, retry_with_backoff, ensure_directories_exist,
    get_recent_matchups, pick_background_music, upload_to_youtube, cleanup_temp_files,
    pick_rotating_tags, MAX_RETRIES, RETRY_DELAY, YOUTUBE_CATEGORY_ID,
    YOUTUBE_PRIVACY_STATUS, YOUTUBE_MADE_FOR_KIDS, VIDEO_CODEC, AUDIO_CODEC,
    VIDEO_PRESET, MUSIC_VOLUME, SFX_VOLUME, AVOID_REPEAT_LOOKBACK, AVOID_REPEAT_MAX_ATTEMPTS,
)

load_dotenv()

BATTLE_WIDTH = int(os.getenv('BATTLE_VIDEO_WIDTH', '1080'))
BATTLE_HEIGHT = int(os.getenv('BATTLE_VIDEO_HEIGHT', '1920'))
BATTLE_FPS = int(os.getenv('BATTLE_VIDEO_FPS', '60'))
BATTLE_MAX_SECONDS = int(os.getenv('BATTLE_MAX_SECONDS', '32'))
BATTLE_MIN_SECONDS = int(os.getenv('BATTLE_MIN_SECONDS', '14'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(base_dir, 'battle_debug.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

BATTLE_TITLE_TEMPLATES = [
    "{names} — Battle Royale! Who Survives?",
    "{n}-Way Battle Royale: {names}",
    "Only One Walks Out: {names}",
    "{names} — Last One Standing #shorts",
    "Can {winner} Survive the Arena?",
]

BATTLE_DESCRIPTION_TEMPLATES = [
    "{names} drop into a shrinking arena — only one walks out!\n"
    "Survivor: {winner} 🏆\n\n"
    "Fully generated battle, zero footage, zero copyright risk. New arena every upload.",

    "🌀⚔️ {names} just fought it out in a randomly generated shrinking-zone arena!\n\n"
    "🏆 Survivor: {winner}\n\n"
    "No script, no real footage — just pure chaotic physics. New battle every day!",

    "The zone closes in, the weapons run out fast... 💥\n\n"
    "{names}\n"
    "🏆 {winner} is the last one standing!\n\n"
    "Every arena, every racer, every outcome — 100% randomly generated.",

    "🎲 Random arena. Shrinking zone. One survivor.\n\n"
    "{names} → {winner} wins!\n\n"
    "New chaos every single upload — who do you think should've survived?",
]

BATTLE_HASHTAG_POOL = [
    "#shorts", "#battleroyale", "#lastonestanding", "#satisfying", "#elimination",
    "#physics", "#fyp", "#viral", "#whowins", "#simulation", "#arena",
]


def _pick_battle_tags(count=6):
    return ' '.join(random.sample(BATTLE_HASHTAG_POOL, min(count, len(BATTLE_HASHTAG_POOL))))


def build_battle_title_and_description(racer_names, winner_name):
    names_joined = " vs ".join(racer_names)
    template = random.choice(BATTLE_TITLE_TEMPLATES)
    title = template.format(names=names_joined, n=len(racer_names), winner=winner_name)[:95]

    racer_tags = ' '.join(f"#{name.lower()}" for name in racer_names[:3])
    hashtags = f"{racer_tags} {_pick_battle_tags()}"
    body = random.choice(BATTLE_DESCRIPTION_TEMPLATES).format(names=names_joined, winner=winner_name)
    description = f"{body}\n\n{hashtags}"
    tags = list(racer_names) + ["battle royale", "elimination arena", "physics simulation", "shorts"]
    return title, description, tags


def generate_battle_video(skip_upload: bool = False, n_racers: int = None):
    try:
        logger.info("⚔️ Battle Royale видео құру процессі басталды")

        ensure_directories_exist()
        cleanup_temp_files()

        recent_matchups = get_recent_matchups(AVOID_REPEAT_LOOKBACK)

        seed = random.randint(1, 2**31 - 1)
        race = simulate_battle(
            w=BATTLE_WIDTH, h=BATTLE_HEIGHT, seed=seed, fps=BATTLE_FPS,
            max_seconds=BATTLE_MAX_SECONDS, min_seconds=BATTLE_MIN_SECONDS,
            n_racers=n_racers,
        )
        racer_names = [r["name"] for r in race["racers"]]

        attempts = 1
        while frozenset(racer_names) in recent_matchups and attempts < AVOID_REPEAT_MAX_ATTEMPTS:
            seed = random.randint(1, 2**31 - 1)
            race = simulate_battle(
                w=BATTLE_WIDTH, h=BATTLE_HEIGHT, seed=seed, fps=BATTLE_FPS,
                max_seconds=BATTLE_MAX_SECONDS, min_seconds=BATTLE_MIN_SECONDS,
                n_racers=n_racers,
            )
            racer_names = [r["name"] for r in race["racers"]]
            attempts += 1
        if attempts > 1:
            logger.info(f"🔁 Қайталанатын құрам аттап өтілді ({attempts} әрекет)")

        winner_name = race["winner_name"]
        logger.info(f"⚔️ Battle ({race['n_racers']}): {' vs '.join(racer_names)} — жеңімпаз: {winner_name}")

        video_title, video_description, video_tags = build_battle_title_and_description(
            racer_names, winner_name
        )
        logger.info(f"🏷️ Тақырып: {video_title}")

        thumbnail_path = os.path.join(base_dir, "battle_thumbnail.jpg")
        try:
            generate_thumbnail(race, thumbnail_path, caption="LAST ONE STANDING?",
                                banner_color=(180, 40, 40), badge_text=f"{race['n_racers']}-WAY BATTLE ROYALE")
            logger.info("✓ Custom thumbnail дайын")
        except Exception as e:
            logger.warning(f"⚠️ Thumbnail генерациясы сәтсіз: {e}")
            thumbnail_path = None

        battle_clip = None
        cold_open_clip = None
        music_clip = None
        sfx_clip = None
        final_video = None

        try:
            battle_clip = build_battle_clip(race)
            duration = battle_clip.duration

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
            main_video = battle_clip.with_audio(final_audio)

            cold_open_clip = build_battle_cold_open_clip(race)
            cold_open_audio_arr = build_cold_open_sfx(cold_open_clip.duration)
            cold_open_audio = AudioArrayClip(cold_open_audio_arr, fps=SFX_SR).subclipped(0, cold_open_clip.duration)
            cold_open_clip = cold_open_clip.with_audio(cold_open_audio)

            final_video = concatenate_videoclips([cold_open_clip, main_video])

            final_output = os.path.join(base_dir, "final_battle.mp4")
            total_duration = duration + cold_open_clip.duration
            logger.info(f"\n⏳ Видео құрылуда ({VIDEO_CODEC}, {BATTLE_FPS}fps, {total_duration:.1f}с)...")

            try:
                final_video.write_videofile(
                    final_output,
                    codec=VIDEO_CODEC,
                    audio_codec=AUDIO_CODEC,
                    fps=BATTLE_FPS,
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
                    fps=BATTLE_FPS,
                    preset='ultrafast'
                )

            logger.info(f"✓ Видео дайын: {final_output}")

            if not skip_upload:
                video_id = retry_with_backoff(lambda: upload_to_youtube(final_output, video_title, video_description, video_tags, thumbnail_path))
                video_url = f"https://youtube.com/shorts/{video_id}"
                send_telegram(
                    f"✅ <b>Жаңа Battle Royale видео жүктелді!</b>\n"
                    f"⚔️ <b>{' vs '.join(racer_names)}</b>\n"
                    f"🏆 Жеңімпаз: {winner_name}\n"
                    f"🔗 {video_url}"
                )
            else:
                logger.info("✓ Видео сақталды (жүктеу өтіп кетті)")

        finally:
            try:
                if battle_clip:
                    battle_clip.close()
                if cold_open_clip:
                    cold_open_clip.close()
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
        send_telegram(f"❌ <b>Battle Royale видео жасауда қате шықты!</b>\n<code>{str(e)[:300]}</code>")
        raise


if __name__ == "__main__":
    try:
        generate_battle_video()
    except Exception as e:
        logger.error(f"Программа сәтсіз аяқталды: {e}")
