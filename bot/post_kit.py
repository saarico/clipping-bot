"""Build the post kit for an approved clip: title, description, tags, where to post, the campaign
rules to re-check. Posting itself is rico's click until the platform audits are through (SETUP.md)."""
import json
from pathlib import Path

ACCOUNTS = json.loads((Path(__file__).parent.parent / "config" / "accounts.json").read_text())


def kit(clip_name, hook, brief, lane_platforms, caption="", thumb="", options=""):
    def text_for(p):
        # the brief names handles per platform ("YouTube: @HiggsfieldAI + @20VC"): only those go on that platform's post
        tags = " ".join(brief.get("tags_by_platform", {}).get(p) or brief.get("tags", []))
        title = f"{hook.rstrip('.')} {tags}".strip()
        desc = (caption or f"{hook}\n\nFrom the full episode: {brief['links'][0] if brief.get('links') else 'see campaign'}") + f"\n{tags}"
        if brief.get("disclosure"):   # brand campaigns: the paid disclosure goes in the caption too, word for word
            desc += f"\n\n{brief['disclosure']}"
        if brief.get("rider"):
            desc += f"\n{brief['rider']}"
        return title, desc.strip()
    lines = [f"CLIP: {clip_name}", ""]
    if thumb:
        lines += [f"Thumbnail: {thumb} (same folder). YouTube Shorts and TikTok take no file: in the app, pick the LAST frame of the video as the cover, it is this picture. Instagram: upload the PNG as the cover."]
        if options:
            lines += [f"Other frames: {options} shows 4 numbered options. Want one of those (or other words on it)? Say so in the chat, e.g. \"clip 01, option 3\"; the next run swaps it."]
        lines += [""]
    for p in lane_platforms:
        handle = ACCOUNTS.get(p, "?")
        title, desc = text_for(p)
        lines += [f"== {p.upper()} ({handle}) ==", f"Title: {title[:100]}", "Description:", desc, "", ]
    if brief.get("rules"):
        lines += ["Campaign rules to re-check before you press Post:"] + [f"- {r}" for r in brief["rules"][:12]]
    lines += ["", "After posting: paste the post link into the campaign on Content Rewards, then into the POSTED sheet column."]
    return "\n".join(lines)
