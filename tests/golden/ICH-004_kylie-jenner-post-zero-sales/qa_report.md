# Pre-post check: ICH-004_kylie-jenner-post-zero-sales

Made by SYSTEM/TOOLS/qa_check.py. FAIL blocks posting. WARN needs a human look. qa_sheet.png shows one frame per second.

| Check | Result | Evidence |
|---|---|---|
| Format | PASS | 1080x1920, 30 fps, 47.2 s, 16.4 MB |
| Audio | PASS | loudness -14.2 LUFS; peak -0.8 dBFS |
| Cut edges (no clipped words) | PASS | 2 edges checked against the audio |
| Captions cover the whole clip | PASS | 56 captions, first at 0.1 s, last ends 47.1 s of 47.2 s |
| Caption text reads clean | PASS | no stutters, filler or cut-off words |
| Caption spelling | PASS | 97 words checked |
| No pop-up label | PASS | none |
| Nothing said twice | PASS | no repeated lines |
| Opener stands alone | PASS | first caption: "kylie jenner" |
| Ends on a finished sentence | PASS | last caption: "30TH THING." |
| Title | PASS | 2 line(s): "Kylie Jenner posted Bloom for free. Sales didn't move." |
| Faces clear of the title | PASS | checked every 0.5 s |
| Captions off faces | PASS | checked every 0.5 s |
| Picture (black, frozen, flicker) | PASS | 10 shots, all clean |
| Clean first 2 seconds | PASS | no freeze or stray shot |
| Smooth transitions | PASS | 16 planned edges, no stray cuts or flashes |
| Audio timestamps steady | PASS | 2211 packets, every gap is one AAC frame |
| Post text tags | PASS | instagram has @greglav, @theicedcoffeehour; youtube has @GregLaVecchia, @theicedcoffeehour |

**Verdict: PASS**
