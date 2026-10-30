#!/usr/bin/env python3
"""script.json -> TikTok-ready MP4s. Usage: python render.py series/<slug>/script.json [--ep N]"""
import argparse
import asyncio
import hashlib
import json
import math
import os
import random
import subprocess
import sys
import time
import wave
from pathlib import Path

import edge_tts
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import library as L

ROOT = Path(__file__).parent
CACHE = ROOT / "cache" / "tts"
FPS, SR = 30, 24000
LW, LH = 360, 640  # layer the text is drawn on; scene is drawn at 180x320 and doubled, ffmpeg triples to 1080x1920
MAX_SECONDS = 60
TAIL = 0.35  # pause after each spoken line
VOICE = "th-TH-PremwadeeNeural"
BOX = (12, 392, 306, 502)  # text box at 61-78% height, right 15% left clear for TikTok's buttons
PAGE_LINES = 3  # subtitle shows one page of lines at a time, following the voice
FONT_PATH = str(ROOT / "assets" / "fonts" / "unifont-th.otf")
FONT = ImageFont.truetype(FONT_PATH, 16)
SUB_FONT = ImageFont.truetype(FONT_PATH, 32)  # 2x Unifont's native 16px grid keeps glyphs crisp
ANIMS = ("none", "bounce", "float", "shake", "pop")
WIPE = 0.2


# --- validation ---------------------------------------------------------------------------------

def _color_ok(c):
    try:
        L.rgb(c)
        return True
    except (ValueError, AttributeError):
        return False


def validate(spec):
    """Return a list of human-readable errors; empty means the script can be rendered."""
    errs = []
    sprites = spec.get("sprites", {})
    for name, sp in sprites.items():
        rows, pal = sp.get("rows"), sp.get("palette")
        if not rows or not isinstance(pal, dict) or len({len(r) for r in rows}) != 1:
            errs.append(f"sprites.{name}: needs 'palette' and non-empty 'rows' of equal length")
            continue
        bad = {ch for r in rows for ch in r if ch != "." and ch not in pal}
        if bad:
            errs.append(f"sprites.{name}: chars {sorted(bad)} missing from palette")
        errs += [f"sprites.{name}.palette.{k}: bad colour {v!r}" for k, v in pal.items() if not _color_ok(v)]
    eps = spec.get("episodes")
    if not eps:
        return errs + ["episodes: at least one episode required"]
    for e, ep in enumerate(eps):
        if not ep.get("scenes"):
            errs.append(f"episodes[{e}].scenes: at least one scene required")
        for s, sc in enumerate(ep.get("scenes", [])):
            at = f"episodes[{e}].scenes[{s}]"
            say = sc.get("say")
            if not isinstance(say, str) or not say.strip():
                errs.append(f"{at}.say: required")
                say = ""
            if sc.get("bg") not in L.BACKGROUNDS:
                errs.append(f"{at}.bg: {sc.get('bg')!r} not in {list(L.BACKGROUNDS)}")
            for kind in ("actors", "props", "labels"):
                for i, el in enumerate(sc.get(kind, [])):
                    p = f"{at}.{kind}[{i}]"
                    if kind == "actors":
                        if el.get("who") not in L.ACTORS:
                            errs.append(f"{p}.who: {el.get('who')!r} not in {list(L.ACTORS)}")
                        if el.get("pose", "idle") not in L.POSES:
                            errs.append(f"{p}.pose: {el.get('pose')!r} not in {list(L.POSES)}")
                    if kind == "props" and el.get("sprite") not in L.ICONS and el.get("sprite") not in sprites:
                        errs.append(f"{p}.sprite: {el.get('sprite')!r} is neither a built-in icon nor in 'sprites'")
                    if kind == "labels" and not el.get("text"):
                        errs.append(f"{p}.text: required")
                    if el.get("anim", "none") not in ANIMS:
                        errs.append(f"{p}.anim: {el.get('anim')!r} not in {list(ANIMS)}")
                    if "on" in el and el["on"] not in say:
                        errs.append(f"{p}.on: {el['on']!r} does not appear in 'say'")
                    errs += [f"{p}.{k}: bad colour {el[k]!r}" for k in ("color", "hair", "skin") if k in el and not _color_ok(el[k])]
    return errs


# --- speech -------------------------------------------------------------------------------------

async def _synth(text, voice, mp3, js):
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")  # edge-tts ignores proxy env on its own
    com = edge_tts.Communicate(text, voice, boundary="WordBoundary", proxy=proxy)
    audio, words = bytearray(), []
    async for ch in com.stream():
        if ch["type"] == "audio":
            audio += ch["data"]
        elif ch["type"] == "WordBoundary":
            words.append([ch["offset"] / 1e7, ch["duration"] / 1e7, ch["text"]])
    mp3.write_bytes(audio)
    js.write_text(json.dumps(words, ensure_ascii=False))  # written last: its presence marks a complete cache entry


def tts(text, voice):
    """-> (mono float32 samples at SR, [[offset_s, duration_s, word], ...]); cached on disk."""
    CACHE.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(f"{voice}|{text}".encode()).hexdigest()[:16]
    mp3, js = CACHE / f"{key}.mp3", CACHE / f"{key}.json"
    for attempt in range(4):
        if js.exists():
            break
        try:
            asyncio.run(_synth(text, voice, mp3, js))
        except Exception as e:  # edge-tts is an unofficial endpoint: retry transient failures / rate limits
            if attempt == 3:
                raise SystemExit(f"TTS failed for {text!r}: {e}")
            time.sleep(2 ** (attempt + 1))
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp3), "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(pcm, np.int16).astype(np.float32) / 32768, json.loads(js.read_text())


def reveal_points(say, words):
    """[(time, chars_visible)]: as each word is spoken, the subtitle reveals `say` up to that word's end."""
    pts, cur = [], 0
    for off, _, w in words:
        i = say.find(w, cur)
        if i >= 0:  # TTS may normalise a word (e.g. digits) so it isn't found; the next word catches up
            cur = i + len(w)
            pts.append((off, cur))
    return pts


def wrap(text, cuts, font, width):
    """Split text at the given cut positions so each line fits width. Returns [(start, end)]."""
    cuts = sorted({c for c in cuts if 0 < c < len(text)} | {len(text)})
    lines, start = [], 0
    while start < len(text):
        fit = [c for c in cuts if c > start and font.getlength(text[start:c]) <= width]
        # shortcut: a run with no cut that is wider than the box overflows it; fine for TTS-segmented Thai
        end = fit[-1] if fit else next(c for c in cuts if c > start)
        lines.append((start, end))
        start = end
        while start < len(text) and text[start] == " ":
            start += 1
    return lines


# --- drawing ------------------------------------------------------------------------------------

def anim_offset(anim, t, seed):
    if anim == "bounce":
        return 0, -round(abs(math.sin(t * 5 + seed)) * 6)
    if anim == "float":
        return 0, round(math.sin(t * 2 + seed) * 3)
    if anim == "shake":
        return (1 if int(t * FPS) % 4 < 2 else -1), 0
    return 0, 0


def textbox(say, lines, visible):
    """Box showing the page of lines that holds the latest revealed character."""
    page = next(i for i, (s, e) in enumerate(lines) if visible <= e) // PAGE_LINES * PAGE_LINES
    x0, y0, x1, y1 = BOX
    img = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, img.width - 1, img.height - 1), fill=(26, 28, 44, 235), outline=(244, 244, 244), width=2)
    d.rectangle((2, 2, img.width - 3, img.height - 3), outline=(86, 108, 134))
    for n, (s, e) in enumerate(lines[page:page + PAGE_LINES]):
        if visible > s:
            d.text((10, 7 + n * 32), say[s:min(e, visible)], font=SUB_FONT, fill=(244, 244, 244))
    return img


class Scene:
    def __init__(self, sc, spec, voice):
        self.sc, self.spec = sc, spec
        self.say = sc["say"].strip()
        self.pcm, self.words = tts(self.say, voice)
        self.pts = reveal_points(self.say, self.words)
        self.frames = math.ceil((len(self.pcm) / SR + TAIL) * FPS)
        cuts = [c for _, c in self.pts] + [i for i, ch in enumerate(self.say) if ch == " "]
        self.lines = wrap(self.say, cuts, SUB_FONT, BOX[2] - BOX[0] - 20)
        self.bg = L.background(sc["bg"])
        self.talk_end = self.words[-1][0] + self.words[-1][1] if self.words else 0
        self._boxes = {}

    def visible(self, t):
        if t >= self.talk_end:
            return len(self.say)
        return max([c for off, c in self.pts if off <= t], default=0)

    def appears(self, el):
        """Seconds into the scene when an element with "on": "<words>" shows up (0 without "on")."""
        if "on" not in el:
            return 0
        i = self.say.find(el["on"])
        return next((off for off, c in self.pts if c > i), 0)

    def speaking(self, t):
        return any(off <= t < off + dur for off, dur, _ in self.words)

    def frame(self, f, badge):
        t = f / FPS
        img = self.bg.copy().convert("RGBA")
        for i, a in enumerate(self.sc.get("actors", [])):
            if t < self.appears(a):
                continue
            talk = a.get("talk", a["who"] == "cat") and self.speaking(t) and int(t * 8) % 2 == 0
            blink = (f + i * 37) % 100 < 4
            sp = L.actor(a["who"], a.get("pose", "idle"), talk, blink, a.get("color", "blue"),
                         a.get("hair", "#40332a"), a.get("skin", "skin"), a.get("scale", 2), a.get("flip", False))
            bob = (int(t * 2) + i) % 2
            dx, dy = anim_offset(a.get("anim", "none"), t, i)
            img.alpha_composite(sp, (int(a.get("x", 90)) - sp.width // 2 + dx, L.GROUND - sp.height + bob + dy))
        for i, p in enumerate(self.sc.get("props", [])):
            t0 = self.appears(p)
            if t < t0:
                continue
            rows, pal = L.ICONS.get(p["sprite"]) or (self.spec["sprites"][p["sprite"]]["rows"],
                                                     self.spec["sprites"][p["sprite"]]["palette"])
            scale = p.get("scale", 2) + (1 if p.get("anim") == "pop" and t - t0 < 0.15 else 0)
            sp = L.sprite(rows, pal, scale, p.get("flip", False))
            dx, dy = anim_offset(p.get("anim", "none"), t, i)
            img.alpha_composite(sp, (int(p.get("x", 90)) - sp.width // 2 + dx, int(p.get("y", 100)) - sp.height // 2 + dy))
        out = img.resize((LW, LH), Image.Resampling.NEAREST)
        d = ImageDraw.Draw(out)
        for i, lb in enumerate(self.sc.get("labels", [])):
            t0 = self.appears(lb)
            if t < t0:
                continue
            size = lb.get("size", 2) + (1 if lb.get("anim") == "pop" and t - t0 < 0.15 else 0)
            dx, dy = anim_offset(lb.get("anim", "none"), t, i + 7)
            d.text((int(lb.get("x", 90)) * 2 + dx * 2, int(lb.get("y", 60)) * 2 + dy * 2), lb["text"],
                   font=ImageFont.truetype(FONT_PATH, 16 * size), fill=L.rgb(lb.get("color", "white")),
                   anchor="mm", stroke_width=2, stroke_fill=L.OUTLINE[:3])
        vis = self.visible(t)
        if vis:  # no empty box before the first word: frame 0 doubles as the thumbnail
            if vis not in self._boxes:
                self._boxes[vis] = textbox(self.say, self.lines, vis)
            out.alpha_composite(self._boxes[vis], BOX[:2])
        if badge:
            w = int(FONT.getlength(badge)) + 12
            d.rectangle((10, 66, 10 + w, 88), fill=L.OUTLINE[:3], outline=(244, 244, 244))
            d.text((16, 69), badge, font=FONT, fill=(255, 205, 117))
        return out.convert("RGB")


def wipe(img, t):
    """Pixel-block dissolve in from black over the first WIPE seconds of a scene."""
    rng = random.Random(1)
    blocks = [(x, y) for y in range(0, LH, 20) for x in range(0, LW, 20)]
    rng.shuffle(blocks)
    d = ImageDraw.Draw(img)
    for x, y in blocks[: int(len(blocks) * (1 - t / WIPE))]:
        d.rectangle((x, y, x + 19, y + 19), fill=L.OUTLINE[:3])


def blip(n):
    t = np.arange(n) / SR
    return (np.sign(np.sin(2 * np.pi * 1100 * t)) * np.exp(-t * 90) * 0.05).astype(np.float32)


# --- episode ------------------------------------------------------------------------------------

def render_episode(spec, ep, n, total, out_dir):
    voice = spec.get("voice", VOICE)
    scenes = [Scene(sc, spec, voice) for sc in ep["scenes"]]
    secs = sum(s.frames for s in scenes) / FPS
    if secs > MAX_SECONDS:
        raise SystemExit(f"EP{n}: {secs:.1f}s is over {MAX_SECONDS}s; shorten or split the episode")

    spf = SR // FPS
    audio = np.zeros(sum(s.frames for s in scenes) * spf, np.float32)
    pos = 0
    for s in scenes:
        audio[pos:pos + len(s.pcm)] += s.pcm
        for off, _, _ in s.words:
            i = pos + int(off * SR)
            b = blip(min(int(0.03 * SR), len(audio) - i))
            audio[i:i + len(b)] += b
        pos += s.frames * spf
    out_dir.mkdir(parents=True, exist_ok=True)
    wav = out_dir / f"ep{n}.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())

    mp4 = out_dir / f"ep{n}.mp4"
    ff = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{LW}x{LH}", "-r", str(FPS),
         "-i", "-", "-i", str(wav), "-vf", "scale=1080:1920:flags=neighbor", "-c:v", "libx264", "-preset", "medium",
         "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "44100",
         "-movflags", "+faststart", "-shortest", str(mp4)], stdin=subprocess.PIPE)
    badge = f"EP{n}/{total}" if total > 1 else ""
    for k, s in enumerate(scenes):
        for f in range(s.frames):
            img = s.frame(f, badge)
            if k and f / FPS < WIPE:  # no wipe on the first scene: frame 0 is the hook/thumbnail
                wipe(img, f / FPS)
            ff.stdin.write(img.tobytes())
    ff.stdin.close()
    if ff.wait():
        raise SystemExit(f"ffmpeg failed for {mp4}")
    wav.unlink()
    (out_dir / f"ep{n}.txt").write_text(ep.get("caption", "") + "\n", encoding="utf-8")
    print(f"{mp4}  {secs:.1f}s")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("script", type=Path)
    ap.add_argument("--ep", type=int, help="render only this episode (1-based)")
    args = ap.parse_args()
    spec = json.loads(args.script.read_text(encoding="utf-8"))
    errs = validate(spec)
    if errs:
        sys.exit("script.json errors:\n" + "\n".join(f"  - {e}" for e in errs))
    eps = spec["episodes"]
    for n, ep in enumerate(eps, 1):
        if args.ep in (None, n):
            render_episode(spec, ep, n, len(eps), ROOT / "out" / args.script.parent.name)


if __name__ == "__main__":
    main()
