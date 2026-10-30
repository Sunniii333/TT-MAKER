"""Built-in asset library, all drawn in code on a 180x320 canvas: colours, backgrounds, characters, icons."""
import random

from PIL import Image, ImageColor, ImageDraw, ImageFilter

W, H = 180, 320
GROUND = 186  # y where actors' feet touch the floor

# Sweetie-16 palette (CC0) plus a few skin/wood tones. Scripts may use these names or any "#hex".
COLORS = {
    "black": "#1a1c2c", "purple": "#5d275d", "red": "#b13e53", "orange": "#ef7d57",
    "yellow": "#ffcd75", "lime": "#a7f070", "green": "#38b764", "teal": "#257179",
    "navy": "#29366f", "blue": "#3b5dc9", "sky": "#41a6f6", "cyan": "#73eff7",
    "white": "#f4f4f4", "silver": "#94b0c2", "gray": "#566c86", "slate": "#333c57",
    "brown": "#8b5a2b", "wood": "#c47a45", "skin": "#f2c29b", "pink": "#ff9eb0",
}
OUTLINE = (26, 28, 44, 255)


def rgb(c):
    return ImageColor.getrgb(COLORS.get(c, c))


def outline(img):
    """Add the 1px dark outline every sprite gets, so custom and built-in art match."""
    w, h = img.size
    mask = Image.new("L", (w + 2, h + 2), 0)
    mask.paste(img.getchannel("A").point(lambda a: 255 if a else 0), (1, 1))
    out = Image.new("RGBA", (w + 2, h + 2), (0, 0, 0, 0))
    out.paste(OUTLINE, (0, 0, w + 2, h + 2), mask.filter(ImageFilter.MaxFilter(3)))
    out.alpha_composite(img, (1, 1))
    return out


def pixels(rows, palette):
    """Pixel map (one char per pixel, '.' = transparent) -> RGBA image without outline."""
    img = Image.new("RGBA", (len(rows[0]), len(rows)), (0, 0, 0, 0))
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != ".":
                img.putpixel((x, y), rgb(palette[ch]) + (255,))
    return img


def sprite(rows, palette, scale=1, flip=False):
    img = outline(pixels(rows, palette))
    if flip:
        img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    return img.resize((img.width * scale, img.height * scale), Image.Resampling.NEAREST) if scale > 1 else img


# --- characters ---------------------------------------------------------------------------------

POSES = ("idle", "point", "shock", "think", "happy", "sad")
DARK = OUTLINE[:3]


def _face(d, pose, talk, blink, ex, ey, mx, my):
    """Eyes at x=ex[0], ex[1] (row ey), mouth starting at (mx, my). Shared by cat and people."""
    for x in ex:
        if blink:
            d.point([(x - 1, ey + 1), (x, ey + 1)], DARK)
        elif pose == "shock":
            d.rectangle((x - 1, ey - 1, x, ey + 1), DARK)
            d.point((x - 1, ey - 1), (255, 255, 255))
        elif pose == "happy":
            d.point([(x - 1, ey + 1), (x, ey), (x + 1, ey + 1)], DARK)
        elif pose == "think":
            d.rectangle((x + 1, ey - 1, x + 1, ey), DARK)
        else:
            d.rectangle((x, ey, x, ey + 1), DARK)
    if talk or pose == "shock":
        d.rectangle((mx, my, mx + 1, my + 1), DARK)
    elif pose == "happy":
        d.point([(mx - 1, my), (mx, my + 1), (mx + 1, my + 1), (mx + 2, my)], DARK)
    elif pose == "sad":
        d.point([(mx - 1, my + 1), (mx, my), (mx + 1, my), (mx + 2, my + 1)], DARK)
    else:
        d.point([(mx, my), (mx + 1, my)], DARK)


# Left half of the narrator cat; mirrored to make the body, face/tail/paws drawn on top.
CAT_HALF = [
    ".o......", ".oo.....", ".opo....", ".oppoooo", ".ooooodo", "oooooooo", "oooooooo",
    "oooooooo", "ooooowww", ".ooowwww", "..oooooo", "...ooooo", "..oooooo", ".ooooooo",
    ".oooooww", ".ooodoww", "ooooooww", "oooodoww", "oooooooo", "..oo.www",
]
CAT_PAL = {"o": "#ef7d57", "d": "#b8553a", "w": "white", "p": "pink"}
CAT_TAIL = [(16, 18), (17, 18), (17, 17), (18, 17), (18, 16), (18, 15), (19, 15), (19, 14), (19, 13), (18, 12)]


def cat(pose="idle", talk=False, blink=False):
    img = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
    img.paste(pixels([h + h[::-1] for h in CAT_HALF], CAT_PAL), (0, 0))
    d = ImageDraw.Draw(img)
    d.point(CAT_TAIL, rgb(CAT_PAL["o"]))
    d.point((18, 15), rgb(CAT_PAL["d"]))
    d.point([(7, 8), (8, 8)], rgb("pink"))  # nose
    if pose == "point":
        d.rectangle((16, 8, 17, 12), rgb(CAT_PAL["o"]))
        d.rectangle((16, 7, 17, 7), rgb("white"))
    if pose == "think":
        d.rectangle((10, 10, 12, 11), rgb("white"))
    _face(d, pose, talk, blink, ex=(4, 11), ey=6, mx=7, my=9)
    return img


def person(kind="kid", pose="idle", talk=False, blink=False, color="blue", hair="#40332a", skin="skin"):
    body_h, leg_h = (10, 9) if kind == "kid" else (14, 15)
    top = 12
    h = top + body_h + leg_h
    img = Image.new("RGBA", (16, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    shirt, sk, hr, pants = rgb(color), rgb(skin), rgb(hair), rgb("slate")
    d.rectangle((3, 1, 12, 11), sk)
    d.rectangle((3, 0, 12, 2), hr)
    d.rectangle((2, 1, 3, 6), hr)
    d.rectangle((12, 1, 13, 6), hr)
    d.rectangle((3, top, 12, top + body_h - 1), shirt)
    d.rectangle((1, top + 1, 2, top + body_h - 1), shirt)
    d.rectangle((1, top + body_h - 2, 2, top + body_h - 1), sk)
    if pose == "point":
        d.rectangle((13, top - 6, 14, top + 1), shirt)
        d.rectangle((13, top - 8, 14, top - 7), sk)
    else:
        d.rectangle((13, top + 1, 14, top + body_h - 1), shirt)
        d.rectangle((13, top + body_h - 2, 14, top + body_h - 1), sk)
    if pose == "think":
        d.rectangle((10, 10, 11, 11), sk)
    d.rectangle((4, top + body_h, 6, h - 2), pants)
    d.rectangle((9, top + body_h, 11, h - 2), pants)
    d.line((3, h - 1, 6, h - 1), DARK)
    d.line((9, h - 1, 12, h - 1), DARK)
    _face(d, pose, talk, blink, ex=(5, 10), ey=6, mx=7, my=9)
    return img


ACTORS = ("cat", "kid", "adult")


def actor(who, pose, talk, blink, color="blue", hair="#40332a", skin="skin", scale=1, flip=False):
    img = cat(pose, talk, blink) if who == "cat" else person(who, pose, talk, blink, color, hair, skin)
    img = outline(img)
    if flip:
        img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    return img.resize((img.width * scale, img.height * scale), Image.Resampling.NEAREST) if scale > 1 else img


# --- icons --------------------------------------------------------------------------------------

ICONS = {
    "coin": (["..YYYY..", ".YyyyyY.", "YywyyyyY", "YyyYYyyY", "YyyYYyyY", "YyyyyyyY", ".YyyyyY.", "..YYYY.."],
             {"Y": "#d8a03a", "y": "yellow", "w": "white"}),
    "heart": ([".rr...rr.", "rRrr.rrrr", "rRrrrrrrr", "rrrrrrrrr", ".rrrrrrr.", "..rrrrr..", "...rrr...", "....r...."],
              {"r": "#e83b3b", "R": "pink"}),
    "star": (["....y....", "....y....", "...yyy...", "yyyyyyyyy", ".yyyyyyy.", "..yyyyy..", "..yy.yy..", ".yy...yy.",
              ".y.....y."], {"y": "yellow"}),
    "house": ([".....rr.....", "....rrrr....", "...rrrrrr...", "..rrrrrrrr..", ".rrrrrrrrrr.", "rrrrrrrrrrrr",
               ".wwwwwwwwww.", ".wccwwwwbbw.", ".wccwwwwbbw.", ".wwwwwwwbbw.", ".wwwwwwwbbw."],
              {"r": "red", "w": "white", "c": "sky", "b": "brown"}),
    "money": (["GGGGGGGGGGGG", "GggggggggggG", "GgggGGGGgggG", "GggGggggGggG", "GgggGGGGgggG", "GggggggggggG",
               "GGGGGGGGGGGG"], {"G": "teal", "g": "green"}),
    "question": ([".wwww.", "ww..ww", "....ww", "...ww.", "..ww..", "..ww..", "......", "..ww..", "..ww.."],
                 {"w": "white"}),
    "exclaim": (["ww", "ww", "ww", "ww", "ww", "ww", "..", "ww", "ww"], {"w": "white"}),
    "check": (["........g", ".......gg", "g.....gg.", "gg...gg..", ".gg.gg...", "..ggg....", "...g....."],
              {"g": "lime"}),
    "cross": (["rr...rr", "rrr.rrr", ".rrrrr.", "..rrr..", ".rrrrr.", "rrr.rrr", "rr...rr"], {"r": "#e83b3b"}),
    "arrow": ([".....w...", ".....ww..", "wwwwwwww.", "wwwwwwwww", "wwwwwwww.", ".....ww..", ".....w..."],
              {"w": "white"}),
}


# --- backgrounds --------------------------------------------------------------------------------

FLOOR = 168


def _floor(d, top, base, line):
    d.rectangle((0, top, W, H), rgb(base))
    for y in range(top + 6, H, 8):
        d.line((0, y, W, y), rgb(line))


def _classroom(d, rng):
    d.rectangle((0, 0, W, FLOOR), rgb("silver"))
    d.rectangle((16, 38, 164, 112), rgb("brown"))
    d.rectangle((20, 42, 160, 108), rgb("teal"))
    for _ in range(6):
        x, y = rng.randrange(28, 130), rng.randrange(50, 100)
        d.line((x, y, x + rng.randrange(8, 24), y), rgb("white"))
    d.ellipse((82, 10, 98, 26), rgb("white"), rgb("black"))
    d.line((90, 18, 90, 13), rgb("black"))
    d.line((90, 18, 94, 18), rgb("black"))
    _floor(d, FLOOR, "wood", "brown")


def _room(d, rng):
    d.rectangle((0, 0, W, FLOOR), rgb("#e8c89a"))
    d.rectangle((108, 38, 162, 96), rgb("white"))
    d.rectangle((112, 42, 158, 92), rgb("sky"))
    d.line((135, 42, 135, 92), rgb("white"), 2)
    d.line((112, 67, 158, 67), rgb("white"), 2)
    d.rectangle((22, 50, 62, 80), rgb("brown"))
    d.rectangle((25, 53, 59, 77), rgb("lime"))
    d.polygon([(28, 77), (40, 60), (52, 77)], rgb("green"))
    _floor(d, FLOOR, "wood", "brown")


def _city(d, rng):
    d.rectangle((0, 0, W, 90), rgb("sky"))
    d.rectangle((0, 90, W, FLOOR), rgb("cyan"))
    x = -4
    while x < W:
        bw, bh = rng.randrange(18, 32), rng.randrange(60, 140)
        d.rectangle((x, FLOOR - bh, x + bw, FLOOR), rgb(rng.choice(["gray", "slate", "navy", "silver"])))
        for wy in range(FLOOR - bh + 4, FLOOR - 4, 6):
            for wx in range(x + 3, x + bw - 2, 5):
                if rng.random() < 0.55:
                    d.rectangle((wx, wy, wx + 1, wy + 2), rgb("yellow"))
        x += bw + rng.randrange(1, 4)
    d.rectangle((0, FLOOR, W, FLOOR + 22), rgb("silver"))
    d.rectangle((0, FLOOR + 22, W, H), rgb("slate"))
    for x in range(0, W, 24):
        d.rectangle((x, FLOOR + 60, x + 12, FLOOR + 62), rgb("white"))


def _nature(d, rng):
    d.rectangle((0, 0, W, 80), rgb("sky"))
    d.rectangle((0, 80, W, FLOOR), rgb("cyan"))
    d.ellipse((128, 18, 154, 44), rgb("yellow"))
    d.ellipse((-60, 110, 120, 230), rgb("green"))
    d.ellipse((70, 120, 260, 240), rgb("teal"))
    d.rectangle((0, FLOOR, W, H), rgb("lime"))
    for _ in range(40):
        x, y = rng.randrange(0, W), rng.randrange(FLOOR + 4, H)
        d.point([(x, y), (x + 1, y - 1), (x + 2, y)], rgb("green"))
    d.rectangle((26, 120, 32, FLOOR), rgb("brown"))
    d.ellipse((10, 86, 50, 128), rgb("green"), rgb("teal"))


def _space(d, rng):
    d.rectangle((0, 0, W, H), rgb("black"))
    for _ in range(90):
        d.point((rng.randrange(W), rng.randrange(FLOOR)), rgb(rng.choice(["white", "yellow", "cyan", "silver"])))
    d.ellipse((112, 28, 160, 76), rgb("red"))
    d.ellipse((120, 34, 140, 50), rgb("orange"))
    d.line((100, 60, 172, 44), rgb("yellow"), 2)
    d.rectangle((0, FLOOR, W, H), rgb("gray"))
    for _ in range(8):
        x, y = rng.randrange(0, W), rng.randrange(FLOOR + 6, H - 10)
        d.ellipse((x, y, x + 14, y + 6), rgb("slate"))


def _office(d, rng):
    d.rectangle((0, 0, W, FLOOR), rgb("#a9c1cf"))
    d.rectangle((14, 30, 74, 100), rgb("white"))
    for y in range(34, 98, 4):
        d.line((16, y, 72, y), rgb("silver"))
    d.rectangle((96, 140, 176, 146), rgb("brown"))
    d.rectangle((100, 146, 104, FLOOR), rgb("brown"))
    d.rectangle((168, 146, 172, FLOOR), rgb("brown"))
    d.rectangle((116, 110, 154, 136), rgb("black"))
    d.rectangle((119, 113, 151, 133), rgb("blue"))
    d.rectangle((133, 136, 137, 140), rgb("black"))
    d.rectangle((150, 22, 170, 42), rgb("white"), rgb("black"))
    _floor(d, FLOOR, "slate", "gray")


def _plain(d, rng):
    d.rectangle((0, 0, W, H), rgb("navy"))
    for y in range(4, H, 10):
        for x in range(4, W, 10):
            d.point((x, y), rgb("slate"))


BACKGROUNDS = {"classroom": _classroom, "room": _room, "city": _city, "nature": _nature,
               "space": _space, "office": _office, "plain": _plain}


def background(name):
    img = Image.new("RGB", (W, H))
    BACKGROUNDS[name](ImageDraw.Draw(img), random.Random(name))  # seeded: same scene looks the same every render
    return img
