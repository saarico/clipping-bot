"""The studio's MAKE stage as separate agents (Studio v2 release 2, board-approved 2026-10-31).

render_clip.main() used to do everything in one 240-line function. It now runs five agents in order,
each owning one job and handing the next a contract file:

  editor    -> edits.json    cut ranges and pieces (dead air out, edges on quiet moments and camera cuts)
  camera    -> frame.json    video.mp4: who is on screen, crop window, pans, punch-ins, overlay layouts
  sound     -> audio.wav     levelled audio, join fades, optional whoosh under card reveals
  graphics  -> cards.json    overlays, number callouts, watermark size, the end hold
  captions  -> captions.ass  hook, who-line, word-timed captions, callout cards (render_clip.build_ass)
  finisher  -> clip.mp4      burns captions + watermark over the picture, muxes the audio, writes .layout.json

The contracts of one render are kept next to the clip as <name>.agents.json so inspectors (release 3) can
check each hand-off on its own. Splitting changed nothing in the output: the golden set and a frame-hash
comparison of old vs new renders are the proof (tests/test_agents.py).
"""
