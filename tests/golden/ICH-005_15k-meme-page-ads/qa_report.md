# Pre-post check: ICH-005_15k-meme-page-ads

Made by SYSTEM/TOOLS/qa_check.py. FAIL blocks posting. WARN needs a human look. qa_sheet.png shows one frame per second.

| Check | Result | Evidence |
|---|---|---|
| Format | PASS | 1080x1920, 30 fps, 50.0 s, 16.7 MB |
| Audio | PASS | loudness -14.1 LUFS; peak -1.3 dBFS |
| Cut edges (no clipped words) | WARN | 14 edges checked against the audio; end 478.15s is loud (59% of speech level); start 505.64s is loud (49% of speech level) |
| Captions cover the whole clip | PASS | 66 captions, first at 0.2 s, last ends 49.9 s of 50.0 s |
| Caption text reads clean | PASS | no stutters, filler or cut-off words |
| Caption spelling | PASS | 94 words checked |
| No pop-up label | PASS | none |
| Nothing said twice | PASS | no repeated lines |
| Opener stands alone | PASS | first caption: "you said that you" |
| Ends on a finished sentence | PASS | last caption: "PARTOOK IN." |
| Title | PASS | 2 line(s): "He bet $15K on ads. It backfired." |
| Faces clear of the title | PASS | checked every 0.5 s |
| Captions off faces | PASS | checked every 0.5 s |
| Picture (black, frozen, flicker) | PASS | 15 shots, all clean |
| Clean first 2 seconds | PASS | no freeze or stray shot |
| Smooth transitions | PASS | 16 planned edges, no stray cuts or flashes |
| Audio timestamps steady | PASS | 2345 packets, every gap is one AAC frame |
| Post text tags | PASS | instagram has @greglav, @theicedcoffeehour; youtube has @GregLaVecchia, @theicedcoffeehour |

**Verdict: PASS with warnings**
