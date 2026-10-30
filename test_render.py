"""Offline self-checks (no TTS, no ffmpeg). Run: python3 test_render.py"""
import json
from pathlib import Path

import library as L
import render as R

# every built-in icon and the example script's sprites are valid pixel maps
for name, (rows, pal) in L.ICONS.items():
    assert len({len(r) for r in rows}) == 1, name
    L.sprite(rows, pal)
for who in L.ACTORS:
    for pose in L.POSES:
        L.actor(who, pose, talk=True, blink=False)

example = json.loads(Path(__file__).with_name("series").joinpath("democratic-socialism", "script.json").read_text())
assert R.validate(example) == [], R.validate(example)

bad = {"sprites": {"x": {"palette": {"a": "red"}, "rows": ["ab", "a"]}},
       "episodes": [{"scenes": [{"bg": "jungle", "say": "สวัสดี", "actors": [{"who": "dog", "pose": "dance"}],
                                 "props": [{"sprite": "nope", "on": "ลาก่อน", "anim": "spin"}]}]}]}
errs = "\n".join(R.validate(bad))
for needle in ("sprites.x", ".bg:", ".who:", ".pose:", ".sprite:", ".on:", ".anim:"):
    assert needle in errs, (needle, errs)

say = "ห้องเรียนนี้ มีคนได้ค่าขนมร้อย"
words = [[0.1, .2, "ห้อง"], [0.3, .2, "เรียน"], [0.5, .1, "นี้"], [0.7, .1, "มี"], [0.8, .1, "คน"],
         [1.0, .1, "ได้"], [1.1, .1, "ค่า"], [1.3, .2, "ขนม"], [1.5, .2, "100"]]  # last word normalised by TTS
pts = R.reveal_points(say, words)
assert pts[2] == (0.5, len("ห้องเรียนนี้")) and len(pts) == 8, pts

lines = R.wrap(say, [c for _, c in pts] + [say.index(" ")], R.SUB_FONT, 120)
assert lines[0][0] == 0 and lines[-1][1] == len(say)
assert all(R.SUB_FONT.getlength(say[s:e]) <= 120 for s, e in lines[:-1]), lines

box = R.textbox(say, lines * 2, len(say))  # more lines than one page must not raise
assert box.size == (R.BOX[2] - R.BOX[0], R.BOX[3] - R.BOX[1])
print("ok")
