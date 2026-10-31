# Pre-post check: ICH-002_what-went-wrong-with-prime

Made by SYSTEM/TOOLS/qa_check.py. FAIL blocks posting. WARN needs a human look. qa_sheet.png shows one frame per second.

| Check | Result | Evidence |
|---|---|---|
| Format | PASS | 1080x1920, 30 fps, 69.7 s, 22.9 MB |
| Audio | PASS | loudness -14.4 LUFS; peak -1.1 dBFS |
| Cut edges (no clipped words) | WARN | 8 edges checked against the audio; end 145.72s is loud (37% of speech level) |
| Captions cover the whole clip | PASS | 79 captions, first at 0.4 s, last ends 69.7 s of 69.7 s |
| Caption text reads clean | WARN | stutter "THAT THAT" |
| Caption spelling | PASS | 109 words checked |
| No pop-up label | PASS | none |
| Nothing said twice | WARN | repeated: "A $50 MILLION BUSINESS IS AWESOME...." (the declared teaser line, heard again in the story; allowed only because rico approved this cut) |
| Opener stands alone | PASS | first caption: "a $50 million" |
| Ends on a finished sentence | PASS | last caption: "POV." |
| Title | PASS | 2 line(s): "What really went wrong with Prime?" |
| Faces clear of the title | PASS | checked every 0.5 s |
| Captions off faces | PASS | checked every 0.5 s |
| Picture (black, frozen, flicker) | PASS | 17 shots, all clean |
| Clean first 2 seconds | PASS | no freeze or stray shot |
| Smooth transitions | PASS | 27 planned edges, no stray cuts or flashes |
| Audio timestamps steady | PASS | 3266 packets, every gap is one AAC frame |
| Post text tags | PASS | instagram has @greglav, @theicedcoffeehour; youtube has @GregLaVecchia, @theicedcoffeehour |

**Verdict: PASS with warnings**
