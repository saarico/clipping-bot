"""What makes a moment entertaining, by genre (rico, 2026-10-28: "go more into different genres and
different types of media", "ensure comedy grade is also present").

A campaign has a media profile (profiles.py: how the footage behaves) and a genre mix (this file:
what the audience came for). The mix comes from the brief and the transcript; the reviewer can pin
it in plan.json brief_overrides "genres": ["comedy", "drama"].

Every window of the transcript gets a score per genre (0-20) from word choice and sentence shape:
  comedy     setup + short punchline, retorts, absurd numbers, insults, sarcasm, laughter, profanity used for effect
  drama      threat, ultimatum, confrontation (second person + imperatives), a reveal
  action     imperatives, countdowns, short loud lines, danger
  horror     fear words, dread, "don't go"
  romance    love, dating, exes, heartbreak
  gossip     famous names, exposed/cheated/beef, "did you see"
  business   money, growth, failure lessons, numbers, deals
  selfhelp   habits, discipline, anxiety, meaning
  truecrime  murder, police, trial, missing
  sports     game, score, champion, coach
  gaming     clutch, insane plays, streamer hype
  music      song, stage, crowd, album

The campaign's entertainment score for a window is the mix-weighted sum of the genre scores, plus
the comedy score whenever comedy is anywhere in the mix (a laugh travels in every genre).
"""
import re

LEX = {
    "comedy": r"\b(stupid|idiot|dumb|moron|loser|ridiculous|absurd|insane|hilarious|joke|kidding|seriously\??|literally|"
              r"technically|obviously|apparently|allegedly|ha+h?a+|lol|lmao|haha|funny|laugh(ed|ing)?|sarcas\w+|bro|dude|"
              r"what the (hell|fuck)|wtf|shut up|no way|are you (kidding|serious)|oh my god|jesus christ|for daddy|sweetheart|buddy|"
              r"fucking|damn|hell|ass|crap|dick|butt|fart|poop|naked|drunk|hungover|cat|dog|goose|pants|underwear|wig|toupee)\b",
    "drama": r"\b(truth|lie[ds]?|lying|secret|betray\w*|dead|die[sd]?|dying|kill\w*|destroy\w*|catastroph\w+|disaster|crash\w*|"
             r"collapse\w*|war|nuclear|danger\w*|threat\w*|no choice|last chance|too late|save the world|end of the world|"
             r"you have to|you need to|or else|promise me|i swear|never again|everything|nothing left|lost everything|"
             r"responsib\w+|fault|blame\w*|forgive\w*|consequenc\w+|sacrific\w+|sir|mr\.|president)\b",
    "action": r"\b(hurry|get (down|out)|shoot|shots? fired|fire|attack\w*|fight\w*|chase[sd]?|explo(de|sion)\w*|bomb\w*|guns?|"
              r"faster|hold on|look out|incoming|countdown|launch\w*|helicopter|jet|missile\w*|crash\w*|escape\w*|hostage\w*|"
              r"rescue\w*|evacuat\w+|emergency|mayday|blow (it |this )?up|take cover|open fire)\b",
    "horror": r"\b(scared|afraid|terrif\w+|creepy|haunted|ghost|demon|monster|dark|blood|scream\w*|nightmare|don't (go|look|open)|"
              r"behind you|something('s| is) (here|wrong)|whisper\w*|basement|woods)\b",
    "romance": r"\b(love[sd]?|loving|kiss\w*|date[sd]?|dating|girlfriend|boyfriend|wife|husband|ex|marri\w+|wedding|cheat\w*|"
               r"breakup|broke up|heart\w*|crush|flirt\w*|text(ed|ing)? (him|her)|first date|soulmate)\b",
    "gossip": r"\b(exposed|caught|leaked|drama|beef|feud|called out|canceled|cancelled|messy|shady|tea|receipts|did you see|"
              r"kardashian|jenner|kanye|taylor swift|drake|beyonce|bieber|rihanna|celebrity|famous|viral|trending|influencer|"
              r"cheated|affair|divorce\w*|scandal|lawsuit|arrested)\b",
    "business": r"\$|\b(million|billion|thousand|revenue|profit|sales|customers?|startup|founder|ceo|investor\w*|raise[ds]?|"
                r"valuation|equity|margin\w*|cash|bankrupt\w*|fired|hired|deal|negotiat\w+|pitch|business|company|market\w*|"
                r"grow(th|ing)?|scale[ds]?|salary|paid|pay|money|rich|broke|price|cost|bought|sold|deck|platform|dollar\w*)\b",
    "selfhelp": r"\b(habit\w*|discipline\w*|motivat\w+|anxiet\w+|anxious|depress\w+|therap\w+|trauma\w*|mindset|purpose|meaning|"
                r"happiness|happy|miserable|confiden\w+|self[- ]?(esteem|worth|doubt)|failure|succeed\w*|success\w*|"
                r"procrastinat\w+|routine|journal\w*|meditat\w+|lesson\w*|advice|mistake\w*|regret\w*)\b",
    "truecrime": r"\b(murder\w*|killer|victim\w*|police|detective\w*|cops?|crime\w*|trial|jury|guilty|innocent|evidence|"
                 r"missing|body|bodies|stab\w*|shot|prison|jail|confess\w*|suspect\w*|case)\b",
    "sports": r"\b(game|match|season|championship|champion\w*|coach\w*|team\w*|score[ds]?|goal\w*|touchdown|home run|"
              r"playoffs?|finals?|mvp|draft\w*|injur\w+|train(ed|ing)?|practice|gym|lift\w*|record|race|win|won|lost|loss)\b",
    "gaming": r"\b(clutch|insane|cracked|goated|gg|ez|chat|stream\w*|rank(ed)?|lobby|respawn|headshot|kill\w*|loot|boss|"
              r"level|speedrun|glitch\w*|lag|noob|pro|gamer|controller|keyboard|twitch|kick)\b",
    "music": r"\b(song\w*|sing\w*|album\w*|track|beat\w*|bars|verse|chorus|hook|stage|crowd|concert|tour\w*|guitar|drum\w*|"
             r"piano|vocal\w*|melody|lyric\w*|band|rapper|producer|studio|record\w*|dj|festival)\b",
}

# brief / transcript wording that points at a genre mix
BRIEF_HINTS = {
    "comedy": r"\b(comedy|comedic|funny|humou?r|laugh\w*|satir\w+|parody|sketch|stand[- ]?up|roast\w*|dark comedy)\b",
    "drama": r"\b(drama\b|dramatic|thriller|tension|intense|emotional|disaster|dark comedy)\b",
    "action": r"\b(action|blockbuster|explos\w+|stunt\w*|chase)\b",
    "horror": r"\b(horror|scary|haunt\w+|slasher|supernatural)\b",
    "romance": r"\b(romance|romantic|rom[- ]?com|dating show|love story|love island|bachelor\w*)\b",
    "gossip": r"\b(celebrity|celebrities|gossip|influencer\w*|reality (tv|show)|kardashian|hollywood|pop culture|tea\b|exposed)\b",
    "business": r"\b(business|money|finance|financial|investing|entrepreneur\w*|startup\w*|founder\w*|marketing|sales|wealth|crypto|bitcoin|vc\b|venture)\b",
    "selfhelp": r"\b(self[- ]?help|self[- ]?improvement|mindset|motivation\w*|psychology|therapy|wellness|productivity|discipline)\b",
    "truecrime": r"\b(true crime|crime|murder|detective|investigation)\b",
    "sports": r"\b(sports?|football|soccer|basketball|nba|nfl|ufc|mma|boxing|fitness|athlete\w*)\b",
    "gaming": r"\b(gaming|gamer\w*|gameplay|twitch|esports|minecraft|fortnite|warzone|roblox|streamer\w*)\b",
    "music": r"\b(music video|musician\w*|concert\w*|album\w*|rapper\w*|singer\w*|the band|festival\w*|live performance\w*|setlist|on stage)\b",
}

SWEAR = r"\b(fuck\w*|shit\w*|bitch\w*|asshole\w*|damn|goddamn|bastard\w*|dick\w*|piss\w*|crap)\b"
RETORT = r"^(what|huh|wait|no|yes|okay|ok|sure|fine|wow|really|right|exactly|seriously|say it|come on|shut up|oh no|oh|well|nope|yep|so\?|and\?)\b[^a-z]{0,3}$"
BIG_NUMBER = r"\b(\d{1,3}(,\d{3})+|\d+ ?(million|billion|trillion|thousand|percent|%)|a (million|billion|trillion|hundred|thousand))\b"


def count(rx, text):
    return len(re.findall(rx, text, flags=re.I))


def detect_mix(text, transcript_text=""):
    """{genre: weight 0-1} for a campaign from its brief (strong) and transcript (weak); at most 3 genres.
    Always at least one genre; 'drama' + 'business' when nothing matches (the podcast default)."""
    low = (text or "").lower()
    tlow = (transcript_text or "").lower()
    pts = {}
    for g, rx in BRIEF_HINTS.items():
        pts[g] = 3.0 * count(rx, low)
    if tlow:
        n = max(len(tlow.split()), 1)
        tp = {g: 1000.0 * count(rx, tlow) / n for g, rx in LEX.items()}
        top_t = max(tp.values()) or 1.0
        for g, v in tp.items():
            pts[g] = pts.get(g, 0) + 3.0 * v / top_t              # the transcript's strongest genre counts like a brief mention
    top = sorted(pts.items(), key=lambda kv: -kv[1])[:3]
    top = [(g, v) for g, v in top if v > 0]
    if not top:
        return {"drama": 0.5, "business": 0.5}
    s = sum(v for _, v in top)
    return {g: round(v / s, 2) for g, v in top}


def comedy(sents, low):
    """0-20: how likely a stranger laughs. Setup + punch (a long line then a short one), retorts,
    absurd big numbers, insults and swearing used for effect, explicit laughter."""
    pts = 0.0
    pts += min(6, 1.5 * count(LEX["comedy"], low))
    pts += min(4, 2 * count(r"\b(ha+h?a+|lol|lmao|laugh\w*)\b", low))
    pts += min(3, 1.5 * count(SWEAR, low))
    pts += min(3, 1.5 * count(BIG_NUMBER, low))
    for a, b in zip(sents, sents[1:]):
        if a["n"] >= 9 and b["n"] <= 5:
            pts += 1.5                                   # setup, then a punch
        if re.match(RETORT, b["text"].strip().lower()):
            pts += 1.0
    if "?" in low and "!" in low:
        pts += 1
    return int(min(20, pts))


def genre_scores(sents, low):
    """{genre: 0-20} for one window of sentences."""
    out = {}
    nw = max(sum(s["n"] for s in sents), 1)
    for g, rx in LEX.items():
        hits = count(rx, low)
        out[g] = int(min(20, 2.5 * hits + 40.0 * hits / nw))
    out["comedy"] = comedy(sents, low)
    # drama also reads sentence shape: second person + imperatives + ultimatums
    you = count(r"\byou('re|'ll|'ve)?\b", low)
    imper = sum(1 for s in sents if re.match(r"^(go|make|tell|say|listen|stop|get|do|don't|give|take|come|look|shut)\b", s["text"].strip().lower()))
    out["drama"] = int(min(20, out["drama"] + min(4, you * 0.5) + min(4, imper * 1.5)))
    return out


def entertainment(sents, low, mix):
    """(0-25 entertainment points for the campaign's mix, {genre: score})."""
    gs = genre_scores(sents, low)
    score = sum(gs[g] * w for g, w in mix.items() if g in gs)
    if "comedy" not in mix:
        score = 0.8 * score + 0.2 * gs["comedy"]           # a laugh travels in every genre
    return int(min(25, score * 1.25)), gs
