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

The profile comes from the reviewer (plan.json brief_overrides "style"), else from the brief text,
else from the footage itself (average shot length, words per second).
"""
import re

PROFILES = {
    "podcast": dict(wps=(2.2, 3.6), pause_penalty=True, filler=True, clarity=True, back_refs=True,
                    length=(30, 55), ok_len=(22, 60), energy=0, quotes=0, reactions=1, cards=True,
                    soft_qa=set()),
    "cinematic": dict(wps=(0.8, 3.8), pause_penalty=False, filler=False, clarity=False, back_refs=False,
                      length=(12, 30), ok_len=(10, 45), energy=6, quotes=10, reactions=1, cards=False,   # rico 2026-10-28: "boring" at 34 s; fan-edit energy = short
                      soft_qa={"Speaker centred", "Somebody in frame", "Smooth transitions", "Clean first 2 seconds", "Audio",
                               "Captions cover the whole clip", "Ends on a finished sentence", "Faces clear of the title",
                               "Cut edges (no clipped words)", "Picture (black, frozen, flicker)"}),   # music under every edge; black title cards. "One 9:16 look" and "Actors fill the frame" are never soft
    "stream": dict(wps=(1.2, 4.2), pause_penalty=False, filler=False, clarity=False, back_refs=False,
                   length=(15, 45), ok_len=(10, 60), energy=10, quotes=4, reactions=3, cards=False,
                   soft_qa={"Speaker centred", "Somebody in frame", "Smooth transitions", "Clean first 2 seconds",
                            "Captions cover the whole clip", "Ends on a finished sentence", "Caption text reads clean"}),
    "performance": dict(wps=(0.0, 9.0), pause_penalty=False, filler=False, clarity=False, back_refs=False,
                        length=(15, 45), ok_len=(10, 60), energy=14, quotes=0, reactions=0, cards=False,
                        soft_qa={"Speaker centred", "Somebody in frame", "Smooth transitions", "Clean first 2 seconds", "Audio",
                                 "Captions cover the whole clip", "Ends on a finished sentence", "Nothing said twice",
                                 "Caption spelling", "Caption text reads clean"}),
}

TEXT_HINTS = {
    "cinematic": r"\b(trailer|trailers|tv spots?|movie|film|in theaters|in cinemas|scene clips?|official clips?|warner|universal|paramount|disney|a24|netflix original|premiere|box office)\b",
    "stream": r"\b(stream|streams|streamer|streamers|twitch|kick|gameplay|gaming|roblox|minecraft|fortnite|warzone|vod|vods|live clipping|react|reacts|reaction)\b",
    "performance": r"\b(concert|concerts|performance|performances|live show|tour|festival|setlist|on stage|acoustic|music video|song|songs|single|album)\b",
    "podcast": r"\b(podcast|podcasts|episode|episodes|interview|interviews|talk show|conversation|guest|host)\b",
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
}


def look(name):
    return LOOK.get(name or "", LOOK["podcast"])


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
