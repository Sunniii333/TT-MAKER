# TT-MAKER

Turns a document (txt/md/pdf) into 16-bit pixel-art TikTok clips (1080x1920, ≤60s each) narrated in Thai.
Claude writes `series/<slug>/script.json`; `render.py` turns it into `out/<slug>/epN.mp4` + `epN.txt` (caption).

## Workflow (per document)

1. User sends a document and says "ทำคลิป".
2. Write `series/<slug>/script.json` (slug: short English kebab-case). Decide the number of episodes from the content.
3. Summarise the script in chat (episode titles + every `say` line) and **wait for the user's OK**. Never render before approval.
4. `python3 render.py series/<slug>/script.json` (`--ep N` for one episode). Fix any errors it prints and rerun.
5. Look at a few frames (`ffmpeg ... -vf select=...,tile`) before sending; send the mp4 + txt files to the user.
6. Commit `series/<slug>/script.json` only. `out/` and `cache/` are gitignored.

Checks: `python3 test_render.py` (offline).

## Writing rules

- Rewrite freely for TikTok pacing, but **never add facts that are not in the source, and never drop the
  source's caveats or the other side's arguments.** If it doesn't fit, add an episode.
- 1 scene = 1 spoken sentence/phrase (≈20–90 Thai chars). Scene length = its voice length, so no timings.
- Scene 1 of each episode is the hook: a question or surprising claim that makes sense in the first 2 seconds.
  Its first frame is the thumbnail, so make it visually busy (big cat, labels, props).
- The last scene teases the next episode ("ตอนหน้า ..."); the final episode ends with a question asking for comments.
- Each episode must be ≤60s. Thai TTS runs about 13 chars/s, so ≈600 chars of `say` per episode. The renderer
  stops with an error if an episode is too long; shorten wording, don't drop arguments.
- `caption`: one line + 3–5 hashtags, include "(ตอน N/M)" for series.

## script.json reference

```json
{
  "series": "title", "voice": "th-TH-PremwadeeNeural",
  "sprites": {"piggy": {"palette": {"p": "pink", "k": "#1a1c2c"}, "rows": ["..pp..", ".pkpp."]}},
  "episodes": [{"title": "EP1 ...", "caption": "... #tag", "scenes": [
    {"bg": "classroom", "say": "ประโยคที่พากย์",
     "actors": [{"who": "cat", "pose": "point", "x": 40}],
     "props":  [{"sprite": "piggy", "x": 100, "y": 140, "scale": 3, "anim": "pop", "on": "กระปุก"}],
     "labels": [{"text": "ทุนนิยม", "x": 90, "y": 70, "size": 2, "color": "yellow", "anim": "pop"}]}
  ]}]
}
```

- `max_seconds` (optional, default 60): per-episode length limit, for when the user asks for longer clips.
- `rate` (optional, default "+0%"): edge-tts speaking rate, e.g. "+15%" to fit more words in.
- Coordinates are on a 180x320 canvas. The scene lives in y 0–186 (floor/feet at y=186); the subtitle box covers
  y≈196–251; keep things out of the top ~50px (TikTok header + EP badge) and right of x≈150 (TikTok buttons).
- `bg`: classroom, room, city, nature, space, office, plain (dark grid, good for numbers/infographics).
- `actors[].who`: `cat` (narrator, lip-syncs automatically), `kid`, `adult`. `pose`: idle, point, shock, think,
  happy, sad. Optional: `x` (centre), `scale` (default 2), `flip`, `color` (shirt), `hair`, `skin`, `talk`, `anim`, `on`.
- `props[].sprite`: built-in icons coin, heart, star, house, money, question, exclaim, check, cross, arrow, or any
  name in `sprites`. Optional: `x`, `y` (centre), `scale` (default 2), `flip`, `anim`, `on`.
- `labels[]`: big text drawn over the scene. `size` 1–3 (default 2); keep ≤ ~10 Thai chars per label.
- `anim`: none, bounce, float, shake, pop (scale-in when it appears).
- `on`: element appears when that exact substring of `say` is spoken.
- Colours: black, purple, red, orange, yellow, lime, green, teal, navy, blue, sky, cyan, white, silver, gray,
  slate, brown, wood, skin, pink, or "#hex".
- Custom `sprites`: one char per pixel, `.` transparent, all rows equal length, ≤ ~24x24. A dark outline is added
  automatically. Draw whatever the topic needs that isn't built in; they stay inside that script.

## Environment notes

- TTS is `edge-tts` (free, unofficial Microsoft endpoint, needs network to `speech.platform.bing.com`). Results are
  cached in `cache/tts/`. The renderer passes `HTTPS_PROXY` to edge-tts itself because edge-tts ignores proxy env.
- Font: `assets/fonts/unifont-th.otf`, a Thai+Latin subset of GNU Unifont (GPL-2+ with font embedding exception).
