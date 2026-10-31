# Pre-post check: ICH-001_20M-house-upgrade

Made by SYSTEM/TOOLS/qa_check.py. FAIL blocks posting. WARN needs a human look. qa_sheet.png shows one frame per second.

| Check | Result | Evidence |
|---|---|---|
| Format | PASS | 1080x1920, 30 fps, 55.6 s, 18.2 MB |
| Audio | PASS | loudness -14.2 LUFS; peak -1.2 dBFS |
| Cut edges (no clipped words) | PASS | 2 edges checked against the audio |
| Captions cover the whole clip | PASS | 82 captions, first at 0.2 s, last ends 55.5 s of 55.6 s |
| Caption text reads clean | PASS | no stutters, filler or cut-off words |
| Caption spelling | PASS | 117 words checked |
| No pop-up label | PASS | none |
| Nothing said twice | PASS | no repeated lines |
| Opener stands alone | PASS | first caption: "so what did you" |
| Ends on a finished sentence | PASS | last caption: "ASSET IN YOUR PORTFOLIO." |
| Title | PASS | 2 line(s): "He bought a $20M house. He already wants an upgrade." |
| Faces clear of the title | PASS | checked every 0.5 s |
| Captions off faces | PASS | checked every 0.5 s |
| Picture (black, frozen, flicker) | PASS | 21 shots, all clean |
| Clean first 2 seconds | PASS | no freeze or stray shot |
| Smooth transitions | WARN | unplanned cut mid-clip at 22.90s (b-roll's own cuts are fine) |
| Audio timestamps steady | PASS | 2606 packets, every gap is one AAC frame |
| Post text tags | PASS | instagram has @greglav, @theicedcoffeehour; youtube has @GregLaVecchia, @theicedcoffeehour |

**Verdict: PASS with warnings**
