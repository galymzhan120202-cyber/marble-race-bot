"""
Long-form "16-Racer Maze Tournament" video generator — single-elimination
bracket built on the same code-only maze-race engine as the Shorts pipeline
(race_sim.py), just landscape and much longer. Independent schedule/cron
from the Shorts (see scheduler.py / .github/workflows/tournament.yml);
shares the YouTube channel, OAuth credentials, Openverse music, SFX
synthesis and Telegram notify helpers with video_gen.py.

Bracket shape: 16 racers -> Round of 16 (4 heats of 4, top 2 per heat
advance) -> Quarterfinals (2 heats of 4, top 2 advance) -> Final (1 heat of
4, winner = champion). A procedurally-drawn bracket board is rendered
between rounds so the tree of matchups is visually trackable, same
code-generated/no-assets style as everything else in this project.
"""
import os
import random
import logging
import traceback

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from moviepy import (
    ImageClip, AudioFileClip, AudioArrayClip, CompositeAudioClip,
    concatenate_videoclips, concatenate_audioclips,
)
from dotenv import load_dotenv

from race_sim import (
    simulate_race, build_race_clip, build_sfx_array, make_racer_icon, get_font,
    pick_theme, build_duck_envelope, race_bump_times, RACER_POOL, SR as SFX_SR,
)
from video_gen import (
    base_dir, send_telegram, retry_with_backoff, ensure_directories_exist,
    pick_background_music, upload_to_youtube, cleanup_temp_files,
    pick_rotating_tags, MAX_RETRIES, RETRY_DELAY, YOUTUBE_CATEGORY_ID,
    YOUTUBE_PRIVACY_STATUS, YOUTUBE_MADE_FOR_KIDS, VIDEO_CODEC, AUDIO_CODEC,
    VIDEO_PRESET, MUSIC_VOLUME, SFX_VOLUME,
)

load_dotenv()

TOUR_WIDTH = int(os.getenv('TOURNAMENT_VIDEO_WIDTH', '1920'))
TOUR_HEIGHT = int(os.getenv('TOURNAMENT_VIDEO_HEIGHT', '1080'))
TOUR_FPS = int(os.getenv('TOURNAMENT_VIDEO_FPS', '30'))
TOUR_ROWS = int(os.getenv('TOURNAMENT_HEAT_ROWS', '32'))
TOUR_HEAT_MIN_SECONDS = int(os.getenv('TOURNAMENT_HEAT_MIN_SECONDS', '18'))
TOUR_HEAT_MAX_SECONDS = int(os.getenv('TOURNAMENT_HEAT_MAX_SECONDS', '55'))

TITLE_CARD_SECONDS = 4.5
HEAT_CARD_SECONDS = 2.6
BRACKET_HOLD_SECONDS = 5.0
CHAMPION_HOLD_SECONDS = 6.5
OUTRO_SECONDS = 4.5

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(base_dir, 'tournament_debug.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

TOURNAMENT_TITLE_TEMPLATES = [
    "16-Racer Maze Tournament — Who's the Champion?",
    "Ultimate Maze Tournament: 16 Racers, 1 Champion!",
    "Maze Race Tournament — Full Bracket Playthrough",
    "16 Racers Enter The Maze... Only 1 Wins The Tournament",
]

TOURNAMENT_DESCRIPTION_TEMPLATES = [
    "16 racers, one single-elimination maze tournament!\n\n"
    "🏁 Round of 16 → Quarterfinals → Final\n"
    "🏆 Champion: {champion}\n\n"
    "Fully code-generated mazes and physics, zero stock footage, zero copyright risk.",

    "The full bracket, start to finish: 4 heats of 4 in the Round of 16, "
    "then Quarterfinals, then one Final heat crowns the champion.\n\n"
    "🏆 This tournament's champion: {champion}\n\n"
    "Every maze is randomly generated — no two tournaments ever play out the same.",

    "🧩🏆 Single-elimination maze tournament — 16 racers enter, only one makes it "
    "through every round.\n\n"
    "Champion: {champion}\n\n"
    "100% procedurally generated: mazes, physics, sound effects — nothing pre-recorded.",
]

TOURNAMENT_HASHTAGS = "#mazerace #tournament #bracket #satisfying #simulation #physics"


def build_tournament_title_and_description(champion_name):
    title = random.choice(TOURNAMENT_TITLE_TEMPLATES)[:95]
    body = random.choice(TOURNAMENT_DESCRIPTION_TEMPLATES).format(champion=champion_name)
    description = f"{body}\n\n{TOURNAMENT_HASHTAGS}"
    tags = ["maze race tournament", "bracket", "physics simulation", "marble race", champion_name]
    return title, description, tags


# --- Card / bracket-board rendering (all code-only, no assets) -----------

def _bg_canvas(theme, w, h):
    img = Image.new("RGBA", (w, h), (*theme["floor"], 255))
    d = ImageDraw.Draw(img)
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([w * 0.25, -h * 0.4, w * 0.75, h * 0.8], fill=(*theme["particle"], 70))
    glow = glow.filter(ImageFilter.GaussianBlur(100))
    img = Image.alpha_composite(img, glow)
    return img


def render_title_card(racers16, theme, seed, w=TOUR_WIDTH, h=TOUR_HEIGHT):
    img = _bg_canvas(theme, w, h)
    d = ImageDraw.Draw(img, "RGBA")
    title_font = get_font(int(h * 0.10))
    sub_font = get_font(int(h * 0.04))
    title = "16-RACER MAZE TOURNAMENT"
    tw = d.textlength(title, font=title_font)
    d.text((w / 2 - tw / 2, h * 0.08), title, font=title_font, fill=(255, 215, 60, 255),
           stroke_width=7, stroke_fill=(0, 0, 0, 255))
    sub = "Single Elimination Bracket"
    sw = d.textlength(sub, font=sub_font)
    d.text((w / 2 - sw / 2, h * 0.20), sub, font=sub_font, fill=(255, 255, 255, 255))

    icon_size = int(h * 0.13)
    cols_ = 8
    rows_ = 2
    grid_w = cols_ * icon_size * 1.15
    x0 = w / 2 - grid_w / 2
    y0 = h * 0.34
    for i, r in enumerate(racers16):
        icon = make_racer_icon(r["color"], icon_size)
        gx, gy = i % cols_, i // cols_
        x = x0 + gx * icon_size * 1.15
        y = y0 + gy * icon_size * 1.3
        img.alpha_composite(icon, (int(x), int(y)))
    return np.array(img.convert("RGB"))


def render_heat_card(round_label, heat_label, heat_racers, theme, w=TOUR_WIDTH, h=TOUR_HEIGHT):
    img = _bg_canvas(theme, w, h)
    d = ImageDraw.Draw(img, "RGBA")
    round_font = get_font(int(h * 0.075))
    heat_font = get_font(int(h * 0.045))
    rw = d.textlength(round_label, font=round_font)
    d.text((w / 2 - rw / 2, h * 0.22), round_label, font=round_font, fill=(255, 215, 60, 255),
           stroke_width=6, stroke_fill=(0, 0, 0, 255))
    hw = d.textlength(heat_label, font=heat_font)
    d.text((w / 2 - hw / 2, h * 0.34), heat_label, font=heat_font, fill=(255, 255, 255, 255))

    icon_size = int(h * 0.20)
    gap = w * 0.02
    total_w = len(heat_racers) * icon_size + gap * (len(heat_racers) - 1)
    x = w / 2 - total_w / 2
    name_font = get_font(int(h * 0.032))
    for r in heat_racers:
        icon = make_racer_icon(r["color"], icon_size)
        img.alpha_composite(icon, (int(x), int(h * 0.48)))
        nw = d.textlength(r["name"], font=name_font)
        d.text((x + icon_size / 2 - nw / 2, h * 0.48 + icon_size + h * 0.02), r["name"],
               font=name_font, fill=(255, 255, 255, 255))
        x += icon_size + gap
    return np.array(img.convert("RGB"))


def render_outro_card(champion, theme, w=TOUR_WIDTH, h=TOUR_HEIGHT):
    img = _bg_canvas(theme, w, h)
    d = ImageDraw.Draw(img, "RGBA")
    icon = make_racer_icon(champion["color"], int(h * 0.22))
    img.alpha_composite(icon, (int(w / 2 - icon.width / 2), int(h * 0.18)))
    title_font = get_font(int(h * 0.06))
    sub_font = get_font(int(h * 0.036))
    title = f"{champion['name']} IS THE CHAMPION!"
    tw = d.textlength(title, font=title_font)
    d.text((w / 2 - tw / 2, h * 0.55), title, font=title_font, fill=(255, 215, 60, 255),
           stroke_width=6, stroke_fill=(0, 0, 0, 255))
    sub = "Thanks for watching — new tournament every few days!"
    sw = d.textlength(sub, font=sub_font)
    d.text((w / 2 - sw / 2, h * 0.68), sub, font=sub_font, fill=(255, 255, 255, 255))
    return np.array(img.convert("RGB"))


def _bracket_box(d, cx, cy, box_w, box_h, heat, theme, font):
    """Draws one heat's box: up to 4 rows of name text, highlighted green
    for racers that advanced (once decided), dim for eliminated ones, or a
    plain 'TBD' placeholder if this heat hasn't been drawn/run yet."""
    x0, y0 = cx - box_w / 2, cy - box_h / 2
    x1, y1 = cx + box_w / 2, cy + box_h / 2
    d.rounded_rectangle([x0, y0, x1, y1], radius=10, fill=(20, 20, 26, 220),
                         outline=(*theme["accent"], 255), width=2)
    if heat is None:
        tbd_font = get_font(int(box_h * 0.22))
        tw = d.textlength("TBD", font=tbd_font)
        d.text((cx - tw / 2, cy - box_h * 0.12), "TBD", font=tbd_font, fill=(150, 150, 160, 255))
        return
    racers = heat["racers"]
    advancing = heat.get("advancing_idx")
    row_h = box_h / len(racers)
    for i, r in enumerate(racers):
        ry = y0 + i * row_h
        is_adv = advancing is not None and i in advancing
        if advancing is not None:
            bg = (40, 130, 70, 200) if is_adv else (10, 10, 12, 140)
            d.rectangle([x0 + 2, ry + 1, x1 - 2, ry + row_h - 1], fill=bg)
        color = r["color"] if (advancing is None or is_adv) else (110, 110, 115)
        d.ellipse([x0 + 8, ry + row_h * 0.18, x0 + 8 + row_h * 0.64, ry + row_h * 0.82],
                  fill=(*color, 255))
        text_color = (255, 255, 255, 255) if (advancing is None or is_adv) else (150, 150, 155, 255)
        d.text((x0 + 14 + row_h * 0.64, ry + row_h * 0.22), r["name"], font=font, fill=text_color)


def render_bracket_board(bracket, theme, caption, w=TOUR_WIDTH, h=TOUR_HEIGHT):
    img = _bg_canvas(theme, w, h)
    d = ImageDraw.Draw(img, "RGBA")
    title_font = get_font(int(h * 0.06))
    cap_font = get_font(int(h * 0.032))
    tw = d.textlength("TOURNAMENT BRACKET", font=title_font)
    d.text((w / 2 - tw / 2, h * 0.03), "TOURNAMENT BRACKET", font=title_font,
           fill=(255, 215, 60, 255), stroke_width=5, stroke_fill=(0, 0, 0, 255))
    cw = d.textlength(caption, font=cap_font)
    d.text((w / 2 - cw / 2, h * 0.115), caption, font=cap_font, fill=(255, 255, 255, 255))

    box_w, box_h = w * 0.19, h * 0.155
    box_font = get_font(int(box_h * 0.16))
    col_x = [w * 0.13, w * 0.38, w * 0.63, w * 0.87]
    r1_ys = [h * (0.24 + 0.19 * i) for i in range(4)]
    r2_ys = [(r1_ys[0] + r1_ys[1]) / 2, (r1_ys[2] + r1_ys[3]) / 2]
    final_y = (r2_ys[0] + r2_ys[1]) / 2

    def _connector(x0, y0, x1, y1):
        mid_x = (x0 + x1) / 2
        d.line([(x0, y0), (mid_x, y0)], fill=(*theme["accent"], 200), width=3)
        d.line([(mid_x, y0), (mid_x, y1)], fill=(*theme["accent"], 200), width=3)
        d.line([(mid_x, y1), (x1, y1)], fill=(*theme["accent"], 200), width=3)

    for i in range(4):
        _connector(col_x[0] + box_w / 2, r1_ys[i], col_x[1] - box_w / 2, r2_ys[i // 2])
    for i in range(2):
        _connector(col_x[1] + box_w / 2, r2_ys[i], col_x[2] - box_w / 2, final_y)
    _connector(col_x[2] + box_w / 2, final_y, col_x[3] - box_w / 2, final_y)

    for i in range(4):
        _bracket_box(d, col_x[0], r1_ys[i], box_w, box_h, bracket["round1"][i], theme, box_font)
    for i in range(2):
        _bracket_box(d, col_x[1], r2_ys[i], box_w, box_h, bracket["round2"][i], theme, box_font)
    _bracket_box(d, col_x[2], final_y, box_w, box_h, bracket["final"], theme, box_font)

    champion = bracket.get("champion")
    cx, cy = col_x[3], final_y
    if champion is None:
        d.ellipse([cx - box_h * 0.22, cy - box_h * 0.22, cx + box_h * 0.22, cy + box_h * 0.22],
                  outline=(150, 150, 160, 255), width=3)
    else:
        icon = make_racer_icon(champion["color"], int(box_h * 0.55))
        img.alpha_composite(icon, (int(cx - icon.width / 2), int(cy - icon.height * 0.85)))
        champ_font = get_font(int(box_h * 0.16))
        d2 = ImageDraw.Draw(img, "RGBA")
        label = "CHAMPION"
        lw = d2.textlength(label, font=champ_font)
        d2.text((cx - lw / 2, cy + box_h * 0.10), label, font=champ_font, fill=(255, 215, 60, 255))
        nw = d2.textlength(champion["name"], font=champ_font)
        d2.text((cx - nw / 2, cy + box_h * 0.30), champion["name"], font=champ_font, fill=(255, 255, 255, 255))

    return np.array(img.convert("RGB"))


# --- Heat execution ---------------------------------------------------

def _run_heat(seed, heat_racers, theme_seed):
    race = simulate_race(
        w=TOUR_WIDTH, h=TOUR_HEIGHT, seed=seed, fps=TOUR_FPS,
        max_seconds=TOUR_HEAT_MAX_SECONDS, min_seconds=TOUR_HEAT_MIN_SECONDS,
        forced_racers=heat_racers, required_finishers=min(2, len(heat_racers)),
        rows=TOUR_ROWS,
    )
    clip = build_race_clip(race)
    sfx_array, sfx_sr = build_sfx_array(race)
    sfx_clip = AudioArrayClip(sfx_array, fps=sfx_sr).subclipped(0, clip.duration)
    clip = clip.with_audio(sfx_clip.with_volume_scaled(SFX_VOLUME))
    return race, clip


def _static_clip(img_array, duration):
    clip = ImageClip(img_array, duration=duration)
    clip.fps = TOUR_FPS
    return clip


# --- Orchestration ------------------------------------------------------

def generate_tournament_video(skip_upload: bool = False):
    try:
        logger.info("🏆 Tournament видео құру процессі басталды")
        ensure_directories_exist()
        cleanup_temp_files()

        seed = random.randint(1, 2**31 - 1)
        rng = random.Random(seed)
        theme = pick_theme(seed)
        racers16 = rng.sample(RACER_POOL, 16)

        bracket = {"round1": [None] * 4, "round2": [None] * 2, "final": None, "champion": None}

        clips = []
        global_bump_times = []
        cumulative_time = 0.0

        def _append(clip, bump_times_local=None):
            nonlocal cumulative_time
            clips.append(clip)
            if bump_times_local:
                global_bump_times.extend(cumulative_time + t for t in bump_times_local)
            cumulative_time += clip.duration

        _append(_static_clip(render_title_card(racers16, theme, seed), TITLE_CARD_SECONDS))

        # Round of 16
        round1_groups = [racers16[i:i + 4] for i in range(0, 16, 4)]
        round1_advancers = []
        for hi, group in enumerate(round1_groups):
            _append(_static_clip(
                render_heat_card("ROUND OF 16", f"Heat {hi + 1} of 4", group, theme), HEAT_CARD_SECONDS))
            heat_seed = seed * 1000 + 100 + hi
            race, clip = _run_heat(heat_seed, group, seed)
            _append(clip, race_bump_times(race))
            top2 = race["full_ranking"][:2]
            bracket["round1"][hi] = {"racers": group, "advancing_idx": top2}
            round1_advancers.append([group[i] for i in top2])
            logger.info(f"🏁 R16 Heat {hi + 1}: {[r['name'] for r in group]} → advance: "
                        f"{[group[i]['name'] for i in top2]}")

        _append(_static_clip(render_bracket_board(bracket, theme, "Round of 16 complete"), BRACKET_HOLD_SECONDS))

        # Quarterfinals
        qf_groups = [round1_advancers[0] + round1_advancers[1], round1_advancers[2] + round1_advancers[3]]
        qf_advancers = []
        for hi, group in enumerate(qf_groups):
            _append(_static_clip(
                render_heat_card("QUARTERFINALS", f"Heat {hi + 1} of 2", group, theme), HEAT_CARD_SECONDS))
            heat_seed = seed * 1000 + 200 + hi
            race, clip = _run_heat(heat_seed, group, seed)
            _append(clip, race_bump_times(race))
            top2 = race["full_ranking"][:2]
            bracket["round2"][hi] = {"racers": group, "advancing_idx": top2}
            qf_advancers.append([group[i] for i in top2])
            logger.info(f"🏁 QF Heat {hi + 1}: {[r['name'] for r in group]} → advance: "
                        f"{[group[i]['name'] for i in top2]}")

        _append(_static_clip(render_bracket_board(bracket, theme, "Quarterfinals complete"), BRACKET_HOLD_SECONDS))

        # Final
        final_group = qf_advancers[0] + qf_advancers[1]
        _append(_static_clip(render_heat_card("FINAL", "Championship Heat", final_group, theme), HEAT_CARD_SECONDS))
        heat_seed = seed * 1000 + 300
        race, clip = _run_heat(heat_seed, final_group, seed)
        _append(clip, race_bump_times(race))
        champion_idx = race["full_ranking"][0]
        champion = final_group[champion_idx]
        bracket["final"] = {"racers": final_group, "advancing_idx": [champion_idx]}
        bracket["champion"] = champion
        logger.info(f"🏆 Чемпион: {champion['name']}")

        _append(_static_clip(render_bracket_board(bracket, theme, f"Champion: {champion['name']}!"),
                              CHAMPION_HOLD_SECONDS))
        _append(_static_clip(render_outro_card(champion, theme), OUTRO_SECONDS))

        final_video = concatenate_videoclips(clips, method="chain")
        final_video.fps = TOUR_FPS
        duration = final_video.duration
        logger.info(f"🎬 Толық ұзақтығы: {duration:.1f}с ({duration / 60:.1f} мин)")

        thumbnail_path = os.path.join(base_dir, "tournament_thumbnail.jpg")
        try:
            thumb_img = render_bracket_board(bracket, theme, f"Champion: {champion['name']}!",
                                              w=1280, h=720)
            Image.fromarray(thumb_img).save(thumbnail_path, "JPEG", quality=92)
            logger.info("✓ Tournament thumbnail дайын")
        except Exception as e:
            logger.warning(f"⚠️ Thumbnail генерациясы сәтсіз: {e}")
            thumbnail_path = None

        music_clip = None
        try:
            music_path, music_attribution = pick_background_music(duration)
        except Exception as e:
            logger.warning(f"⚠️ Музыка таңдау қатесі: {e}")
            music_path, music_attribution = None, None

        video_title, video_description, video_tags = build_tournament_title_and_description(champion["name"])

        try:
            final_audio = final_video.audio
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
                    envelope = build_duck_envelope(len(music_array), SFX_SR, global_bump_times)
                    music_clip = AudioArrayClip(music_array * envelope[:, None], fps=SFX_SR)
                except Exception as e:
                    logger.warning(f"⚠️ Ducking қатесі, ducking-сіз жалғастырылады: {e}")

                final_audio = CompositeAudioClip([final_audio, music_clip]) if final_audio else music_clip
                if music_attribution:
                    video_description += f"\n\n{music_attribution}"
                logger.info(f"🎵 Музыка таңдалды: {os.path.basename(music_path)}")
            else:
                logger.warning("⚠️ Фон музыкасы табылмады, тек SFX қолданылады")

            final_with_audio = final_video.with_audio(final_audio) if final_audio else final_video

            final_output = os.path.join(base_dir, "final_tournament.mp4")
            logger.info(f"\n⏳ Видео құрылуда ({VIDEO_CODEC}, {TOUR_FPS}fps, {duration:.1f}с)...")

            try:
                final_with_audio.write_videofile(
                    final_output, codec=VIDEO_CODEC, audio_codec=AUDIO_CODEC,
                    fps=TOUR_FPS, preset=VIDEO_PRESET, logger=None,
                )
            except Exception as write_error:
                logger.warning(f"⚠️ Видео жазу қатесі: {write_error}")
                logger.info("   Резервтік кодек қолданылуда...")
                final_with_audio.write_videofile(
                    final_output, codec="mpeg4", audio_codec="libmp3lame",
                    fps=TOUR_FPS, preset='ultrafast',
                )

            logger.info(f"✓ Видео дайын: {final_output}")

            if not skip_upload:
                video_id = retry_with_backoff(lambda: upload_to_youtube(
                    final_output, video_title, video_description, video_tags, thumbnail_path))
                video_url = f"https://youtube.com/watch?v={video_id}"
                send_telegram(
                    f"✅ <b>Жаңа Tournament видео жүктелді!</b>\n"
                    f"🏆 Чемпион: {champion['name']}\n"
                    f"⏱️ Ұзақтығы: {duration / 60:.1f} мин\n"
                    f"🔗 {video_url}"
                )
            else:
                logger.info("✓ Видео сақталды (жүктеу өтіп кетті)")

        finally:
            try:
                final_video.close()
                if music_clip:
                    music_clip.close()
            except Exception:
                pass

    except Exception as e:
        logger.error(f"❌ Қате: {e}")
        logger.debug(traceback.format_exc())
        send_telegram(f"❌ <b>Tournament видео жасауда қате шықты!</b>\n<code>{str(e)[:300]}</code>")
        raise


if __name__ == "__main__":
    try:
        generate_tournament_video()
    except Exception as e:
        logger.error(f"Программа сәтсіз аяқталды: {e}")
