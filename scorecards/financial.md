# Financial scorecard: is this campaign worth joining?

rico asked for this on 2026-10-26, before the second campaign scan: "determine the rules for selecting a proper and worthwhile campaign, whether the personality is popular enough to get those viewers, what the content is and if it's worth making, with research and a background check, and whether the engagement is there to make a video explode."

A campaign is a bet of our time against views we don't control. We only join when all four legs hold: **it pays, people will watch, we can make the clips, and the rules won't eat the payout.** The scoring below is run by `bot/campaign_score.py`; the research steps are done by Claude before the score is trusted.

## 1. Hard stops (any one = skip, no score)
| Stop | Why |
|---|---|
| Pays below $0.75 per 1k views, or a CPM "auction"/pool with no fixed rate | Below $0.75 a 15k-view Short earns about $10 before the 10% fee; auctions can pay almost nothing per view |
| Budget left under $1,000, or 3 days or less left | Campaigns end the moment the budget is gone, and clips in the queue earn nothing |
| Pay-to-join, or must buy a product/course to clip | Never pay to work |
| Platforms don't include at least one of our lanes (YouTube business, Instagram celebrity, TikTok streamers/music/gaming) | Our accounts are built per lane; off-lane posts hurt the account (README "Channel lanes") |
| Audience rule we can't meet (e.g. "60% of viewers in Turkey", "French posts") | Views that don't count are unpaid work |
| Content we won't post: gambling, adult, political, crypto pumps, supplements with health claims | Platform bans and account strikes outlast any campaign |
| "Application required" with no public brief | We can't check the rules before committing time |
| Creator or brand with a recent scandal, lawsuit, or platform ban in progress | Their reach can vanish mid-campaign, and our account carries the association |

## 2. Score (0–100). **JOIN NOW** = 70+ with proof clips already get views (D 15+) and $10k+ budget left: the one to join for sure. JOIN = 70+. MAYBE = 55–69, only if a lane has nothing better. SKIP under 55. A hard stop is shown as STOP whatever the score.

Scorecard audit 2026-10-26 (rico): removed the free 3 points for a normal minimum payout, added crowding (budget per clipper), capped rules load at 0–10, stops always shown before the number, and the $/clip estimate uses our own 7-day median once posts.csv has it.
| Leg | Points | What earns them | How we check |
|---|---|---|---|
| **A. Pay and budget** | 25 | Rate: $2+ = 10, $1.50 = 8, $1 = 5, $0.75 = 2. Budget left: $10k+ = 8, $5k = 6, $2k = 3. Crowding, budget left per clipper already in: $100+ = 4, $30+ = 2, less = 0 (unknown = 2). Caps: max per clip $300+ or none = 2, min payout $1.50 or lower = 1 | Campaign card + main page (clipper count is on the public page) |
| **B. Creator reach** (will people watch?) | 25 | Followers on the clip platform: 1M+ = 10, 250k = 7, 50k = 4, under 20k = 0. Average views per recent long video vs followers (engagement): over 20% = 8, 5–20% = 5, under 5% = 1. Search interest rising this month (Google Trends, news) = 7, flat = 3, falling = 0 | Their channel/profile, Social Blade, Google Trends, news search |
| **C. Clip supply** (is there a video worth cutting?) | 20 | Long-form library of 10+ episodes with talking-head segments = 8. Stories a stranger understands in one sentence (money, celebrity, drama, a number) = 7. The show's own b-roll/graphics to reuse = 5 | Watch 2 episodes; count stories that pass STORY_STRUCTURE's 4 questions |
| **D. Proof clips explode** (engagement) | 20 | Other clippers' clips of this creator already pull 100k+ = 10, 20k+ = 6, nothing found = 0. Comments and shares visible on those clips (not just views) = 5. Creator reposts or engages with clips = 5 | Search "<creator> clips" on YouTube/TikTok/IG, read the top 10 by views |
| **E. Rules load** | 10 | Plain rules (tags, length, no outside footage) = 10. Audience % rule = -3. Must use their full file / specific episodes only = -2. Must post their promos too = -5. Application needed = -2. Never below 0 | Main campaign page, word for word (PLAYBOOK 19) |

## 3. Background check (done before joining, written into CAMPAIGNS/<campaign>/requirements.md)
1. **Who runs it**: the creator's own team, an agency (Clip Strategy, Clipex, ClipFarm), or the platform. Agency campaigns have paid clippers before; an unknown brand with a $1k budget often never pays out.
2. **Payment history**: search "<campaign or agency> clippers paid" and the Whop/Content Rewards reviews. One pattern of unpaid clippers = stop.
3. **The creator**: last 90 days of news. Lawsuits, bans, "cancelled", health claims. A current scandal can be a view spike, but the account risk is ours.
4. **Content legality**: the creator owns the footage (own podcast = yes; reaction/commentary on someone else's show = murky; music = label rights). We clip only what the campaign owner has the right to license.
5. **Platform fit**: where do this creator's clips already perform (YouTube Shorts vs TikTok vs Reels)? That decides the lane, together with the story topic.

## 4. Worth-it math (write it on the card)
Expected earnings per clip = (our median views on that lane) × (share of views that count) × rate / 1000 × 0.9 (fee).
With a new YouTube account: 15k views × 0.6 counted × $1.25 / 1000 × 0.9 = **$10 per clip**, and about 45 minutes of work per clip now. Under $5 per clip, don't join unless the creator reach (B) is huge and the budget is deep. Re-run this with our own numbers every week from posts.csv.

## 5. After joining
- Copy the MAIN campaign page's rules into requirements.md and tags.json the same day (PLAYBOOK 19).
- First 2 clips are a test: if the first 72 h fall under half of our lane median, stop and move on. The campaign card's budget bar tells you how fast others are eating it.
- The scan logs every offered campaign in data/scan_seen.json. Weekly: rank campaigns by net $ per hour and drop the worst.
