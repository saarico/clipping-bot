"""Grading profiles per kind of footage (rico, 2026-10-28: "a new scoring system for different media").

One profile drives the three graders so that a movie trailer, a stream and a podcast are each judged
by what makes THEM work, not by podcast rules:

  find_moments  which 10-60 s windows are worth cutting (pace targets, what counts as stakes, energy)
  judge_clip    the machine score of the finished clip (length sweet spot, pace, variety)
  qa_check      which checks are hard FAILs and which are warnings

Profiles:
  podcast      talking heads: a speaker must be centred and in frame, cuts must be invisible, the
               story must stand alone (no "as we said in the shame episode"), 30-55 s
  cinematic    movie trailers, scene clips, TV spots: fast cuts and faceless shots are the material,
               music fills pauses, quotable short lines and famous names score, 15-40 s
  stream       streamers, gaming, live reactions: reactions, hype words and loud moments score,
               captions can lag the chaos, 15-45 s
  performance  concerts, music, live performance: audio energy is the story, lyrics are not graded
               for spelling or repeats, 15-45 s
  talker       one person talking to camera (YouTuber, TikToker, vlog, commentary, rant): the boldest claim
               first, claim -> proof -> lesson, 20-40 s (board deck 2026-10-31)
  serious      news, documentary, explainers, history, true crime, lectures: the fact that shocks, then why and
               what it means; calm, no SFX, story weighs most, 30-60 s (board deck 2026-10-31)
  edit         fan edits, montages, compilations: the strongest picture in frame 1, cut on the beat, no
               spoken story needed, 10-25 s (board deck 2026-10-31)

Board-approved 2026-10-31 (rico: "approve 1 - 3"): every profile also carries its own judge WEIGHTS (how the
100 points of bot/judge_clip.py are split for this kind of content) and the minimum-per-area rule (AREA_MIN):
a clip that scores under half of an area that carries 10+ points is under the bar, whatever its total.

The profile comes from the reviewer (plan.json brief_overrides "style"), else from the brief text,
else from the footage itself (average shot length, words per second).
"""
import re
from pathlib import Path

PROFILES = {
    "podcast": dict(wps=(2.2, 3.6), pause_penalty=True, filler=True, clarity=True, back_refs=True,
                    length=(30, 55), ok_len=(22, 60), energy=0, quotes=0, reactions=1, cards=True,
                    soft_qa=set()),
    "cinematic": dict(wps=(1.3, 3.8), pause_penalty=False, filler=False, clarity=False, back_refs=False,
                      length=(12, 30), ok_len=(10, 45), energy=6, quotes=10, reactions=1, cards=False,   # rico 2026-10-28: "boring" at 34 s; fan-edit energy = short
                      soft_qa={"Smooth transitions", "Clean first 2 seconds",
                               "Captions cover the whole clip", "Ends on a finished sentence", "Faces clear of the title",
                               "Cut edges (no clipped words)", "Picture (black, frozen, flicker)"}),   # 2026-10-29: centring, somebody in frame and audio are hard again   # music under every edge; black title cards. "One 9:16 look" and "Actors fill the frame" are never soft
    "stream": dict(wps=(1.2, 4.2), pause_penalty=False, filler=False, clarity=False, back_refs=False,
                   length=(15, 45), ok_len=(10, 60), energy=10, quotes=4, reactions=3, cards=False,
                   soft_qa={"Smooth transitions", "Clean first 2 seconds",
                            "Captions cover the whole clip", "Ends on a finished sentence", "Caption text reads clean"}),
    "performance": dict(wps=(0.0, 9.0), pause_penalty=False, filler=False, clarity=False, back_refs=False,
                        length=(15, 45), ok_len=(10, 60), energy=14, quotes=0, reactions=0, cards=False,
                        soft_qa={"Speaker centred", "Somebody in frame", "Smooth transitions", "Clean first 2 seconds", "Audio",
                                 "Captions cover the whole clip", "Ends on a finished sentence", "Nothing said twice",
                                 "Caption spelling", "Caption text reads clean"}),   # concerts: crowd shots are the material
    # board deck 2026-10-31: three more kinds of content. The keys are the same ones the rest of the bot reads
    # (clarity=True = a talking show for the opener rule and the face probe; cards=True = still camera + number cards)
    "talker": dict(wps=(2.4, 4.0), pause_penalty=True, filler=True, clarity=True, back_refs=True,
                   length=(20, 40), ok_len=(15, 50), energy=0, quotes=2, reactions=0, cards=True,
                   soft_qa=set()),
    "serious": dict(wps=(2.0, 3.4), pause_penalty=True, filler=True, clarity=True, back_refs=True,
                    length=(30, 60), ok_len=(25, 70), energy=0, quotes=0, reactions=0, cards=True,
                    soft_qa=set()),
    "edit": dict(wps=(0.0, 9.0), pause_penalty=False, filler=False, clarity=False, back_refs=False,
                 length=(10, 25), ok_len=(8, 35), energy=12, quotes=4, reactions=0, cards=False,
                 soft_qa={"Speaker centred", "Smooth transitions", "Clean first 2 seconds", "Captions cover the whole clip",
                          "Ends on a finished sentence", "Nothing said twice", "Caption spelling", "Caption text reads clean"}),
}

# How the judge's 100 points are split per kind of content (board deck slide "Scorecards shift weight to what matters
# for each type", approved 2026-10-31). Areas are bot/judge_clip.py's: each area is measured on its own scale and
# then weighted here. Deck area -> judge areas: Hook = hook; Story & payoff = story; Entertainment = entertainment +
# comedy; Visual & framing = framing + variety; Pace = pace; Captions = captions; Sound = sound; Brief fit = length.
WEIGHTS = {
    "podcast":     dict(hook=20, story=20, entertainment=10, comedy=5, framing=5, variety=5, pace=10, captions=10, sound=5, length=10),
    "talker":      dict(hook=25, story=20, entertainment=10, comedy=5, framing=5, variety=5, pace=10, captions=10, sound=5, length=5),
    "stream":      dict(hook=20, story=10, entertainment=15, comedy=5, framing=8, variety=7, pace=15, captions=5, sound=10, length=5),
    "cinematic":   dict(hook=20, story=15, entertainment=10, comedy=5, framing=10, variety=10, pace=10, captions=5, sound=10, length=5),
    "performance": dict(hook=15, story=10, entertainment=10, comedy=5, framing=12, variety=13, pace=15, captions=5, sound=10, length=5),
    "serious":     dict(hook=20, story=25, entertainment=5, comedy=0, framing=5, variety=5, pace=10, captions=15, sound=5, length=10),
    "edit":        dict(hook=20, story=10, entertainment=10, comedy=5, framing=10, variety=15, pace=15, captions=0, sound=10, length=5),
}
AREA_MIN = (10, 0.5)   # an area weighted 10+ points must score at least half of them, or the clip is under the bar


def weights(name):
    """The judge's weights for a content type: the board's table, or the Analyst's nudged copy (data/weights_tuned.json,
    bot/analyst.py) once enough posted clips of that type have 7-day views. STUDIO_BOARD_WEIGHTS=1 forces the table
    (the golden-set tests use it)."""
    import json
    import os
    key = name if name in WEIGHTS else "podcast"
    if not os.environ.get("STUDIO_BOARD_WEIGHTS"):
        try:
            tuned = json.loads((Path(__file__).resolve().parent.parent / "data" / "weights_tuned.json").read_text())
            w = tuned.get(key, {}).get("weights")
            if w and set(w) == set(WEIGHTS[key]) and sum(w.values()) == 100:
                return w
        except (OSError, ValueError):
            pass
    return WEIGHTS[key]

TEXT_HINTS = {
    "cinematic": r"\b(trailer|trailers|tv spots?|movie|film|in theaters|in cinemas|scene clips?|official clips?|warner|universal|paramount|disney|a24|netflix original|premiere|box office)\b",
    "stream": r"\b(stream|streams|streamer|streamers|twitch|kick|gameplay|gaming|roblox|minecraft|fortnite|warzone|vod|vods|live clipping|react|reacts|reaction)\b",
    "performance": r"\b(concert|concerts|performance|performances|live show|tour|festival|setlist|on stage|acoustic|music video|song|songs|single|album)\b",
    "podcast": r"\b(podcast|podcasts|episode|episodes|interview|interviews|talk show|conversation|guest|host)\b",
    "talker": r"\b(vlogs?|youtubers?|tiktokers?|commentary|commentator|rants?|storytimes?|monologues?|talking heads?|to camera|solo videos?)\b",
    "serious": r"\b(news|documentar(?:y|ies)|investigations?|true crime|history|historical|explainers?|science|lectures?|ted talks?|keynotes?|journalism|current events)\b",
    "edit": r"\b(fan ?edits?|montages?|amvs?|velocity edits?|compilations?|edit style|beat ?sync(?:ed)?|phonk)\b",
}
HYPE = r"\b(insane|clutch|no way|let'?s go|lets go|gg|oh my god|omg|bro|what the|wtf|rage|cooked|cracked|goated|w|l|nah|yo|chat|ez|unreal|sheesh|bruh)\b"


# How the clip looks, per kind of footage (rico, 2026-10-28: "font looks nicer and is relevant").
# Fonts live in bot/fonts (Google Fonts, OFL). cap_group = words per caption phrase (min, max).
LOOK = {
    "podcast": dict(title_font="Montserrat ExtraBold", title_file="Montserrat-ExtraBold.ttf", title_max=84, title_bold=0, title_spacing=0,
                    cap_font="Montserrat Black", cap_bold=0, cap_size=80, outline=7, shadow=2, cap_group=(2, 4), accent="&H00D7FF&"),
    # rico, 2026-10-28 (DIGGER run 4): Bebas Neue + Poppins "isn't nice or good size": back to the heavy Montserrat
    # look the approved ICH clips had, bigger, thicker outline
    "cinematic": dict(title_font="Montserrat ExtraBold", title_file="Montserrat-ExtraBold.ttf", title_max=88, title_bold=0, title_spacing=0,
                      cap_font="Montserrat Black", cap_bold=0, cap_size=86, outline=8, shadow=3, cap_group=(2, 4), accent="&H2BC6FF&"),   # warm gold
    "stream": dict(title_font="Montserrat ExtraBold", title_file="Montserrat-ExtraBold.ttf", title_max=88, title_bold=0, title_spacing=0,
                   cap_font="Montserrat Black", cap_bold=0, cap_size=86, outline=8, shadow=2, cap_group=(2, 4), accent="&H00D7FF&"),
    "performance": dict(title_font="Montserrat ExtraBold", title_file="Montserrat-ExtraBold.ttf", title_max=88, title_bold=0, title_spacing=0,
                        cap_font="Montserrat Black", cap_bold=0, cap_size=84, outline=8, shadow=3, cap_group=(2, 5), accent="&H2BC6FF&"),
    "talker": dict(title_font="Montserrat ExtraBold", title_file="Montserrat-ExtraBold.ttf", title_max=84, title_bold=0, title_spacing=0,
                   cap_font="Montserrat Black", cap_bold=0, cap_size=84, outline=8, shadow=2, cap_group=(2, 4), accent="&H00D7FF&"),
    "serious": dict(title_font="Montserrat ExtraBold", title_file="Montserrat-ExtraBold.ttf", title_max=80, title_bold=0, title_spacing=0,
                    cap_font="Montserrat Black", cap_bold=0, cap_size=76, outline=6, shadow=2, cap_group=(3, 5), accent="&HFFFFFF&"),   # calm: white keywords
    "edit": dict(title_font="Montserrat ExtraBold", title_file="Montserrat-ExtraBold.ttf", title_max=88, title_bold=0, title_spacing=0,
                 cap_font="Montserrat Black", cap_bold=0, cap_size=86, outline=8, shadow=3, cap_group=(1, 3), accent="&H2BC6FF&"),
}


LOOK_KEYS = ("title_max", "cap_size", "outline", "shadow", "cap_group", "accent", "title_spacing")


def look(name, overrides=None):
    """The profile's look, with the campaign's own overrides on top (plan.json brief_overrides "look":
    {"accent": "&H2BC6FF&" (ASS BGR), "cap_size": 86, "cap_group": [2, 4], "title_max": 88, "outline": 8, "shadow": 3}).
    Fonts stay Montserrat (rico's rule 31); only sizes, colours and grouping change per campaign."""
    base = dict(LOOK.get(name or "", LOOK["podcast"]))
    for k, v in (overrides or {}).items():
        if k not in LOOK_KEYS or v in (None, ""):
            continue
        if k == "cap_group":
            if isinstance(v, (list, tuple)) and len(v) == 2 and all(isinstance(x, int) and 1 <= x <= 8 for x in v) and v[0] <= v[1]:
                base[k] = (int(v[0]), int(v[1]))
        elif k == "accent":
            if isinstance(v, str) and re.fullmatch(r"&H[0-9A-Fa-f]{6}&", v):
                base[k] = v.upper().replace("&H", "&H")
        elif isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 400:
            base[k] = int(v)
        # anything else (a string size, a CSS colour, a one-item group) keeps the profile's value: a bad look must never kill a render
    return base


def profile(name):
    return PROFILES.get(name or "", PROFILES["podcast"])


def detect_from_text(text):
    """Best profile for a brief's wording; '' when nothing in the text points anywhere."""
    low = (text or "").lower()
    hits = {k: len(re.findall(rx, low)) for k, rx in TEXT_HINTS.items()}
    best = max(hits, key=hits.get)
    return best if hits[best] >= 2 and hits[best] > hits["podcast"] / 2 else ("podcast" if hits["podcast"] >= 2 else "")


def detect_from_footage(words, duration, shot_len=None):
    """Fallback from the footage itself: fast cuts = cinematic, few words = performance, else podcast."""
    wps = len(words or []) / max(duration, 1)
    if shot_len is not None and shot_len < 2.5 and wps < 2.0:
        return "cinematic"
    if wps < 0.8:
        return "performance"
    return "podcast"


def resolve(brief, words=None, duration=0.0, shot_len=None):
    """The profile name to use: reviewer override, brief wording, then the footage."""
    if brief.get("style") in PROFILES:
        return brief["style"]
    t = detect_from_text(brief.get("text", "") + " " + " ".join(brief.get("rules", [])))
    if t:
        return t
    return detect_from_footage(words, duration, shot_len) if duration else "podcast"
