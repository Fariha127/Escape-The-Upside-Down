"""Cut a transparent character sheet into one PNG per character (run once, by hand).

    python tools/split_sprites.py path/to/sheet.png [path/to/mind_flayer.png]

Needs only pygame. The sheet must have a transparent background. Figures are found as separate blobs of
pixels and named in reading order (left to right, top to bottom) with NAMES below. If your sheet is laid out
differently, change NAMES or run it and rename the files by hand. Output: assets/characters/<name>.png"""
from __future__ import annotations
import sys
from collections import deque
from pathlib import Path

import pygame

NAMES = ("vecna", "demogorgon", "demogorgon_2", "eleven", "lucas", "mike", "will", "dustin")
OUT = Path(__file__).resolve().parent.parent / "assets" / "characters"
MIN_SIZE = 20            # blobs smaller than this (pixels) are specks, not characters
MARGIN = 6               # a speck this close to a character belongs to it
ALPHA_MIN = 10


def blobs(img: pygame.Surface):
    """Connected groups of non-transparent pixels as (left, top, right, bottom) boxes."""
    w, h = img.get_size()
    solid = [[img.get_at((x, y)).a > ALPHA_MIN for x in range(w)] for y in range(h)]
    seen = [[False] * w for _ in range(h)]
    boxes = []
    for y in range(h):
        for x in range(w):
            if solid[y][x] and not seen[y][x]:
                q, box = deque([(x, y)]), [x, y, x, y]
                seen[y][x] = True
                while q:
                    cx, cy = q.popleft()
                    box = [min(box[0], cx), min(box[1], cy), max(box[2], cx), max(box[3], cy)]
                    for dx in (-1, 0, 1):
                        for dy in (-1, 0, 1):
                            nx, ny = cx + dx, cy + dy
                            if 0 <= nx < w and 0 <= ny < h and solid[ny][nx] and not seen[ny][nx]:
                                seen[ny][nx] = True
                                q.append((nx, ny))
                boxes.append(box)
    return boxes


def characters(img: pygame.Surface):
    """Big blobs, with nearby specks merged in, in reading order."""
    boxes = blobs(img)
    big = [b for b in boxes if max(b[2] - b[0], b[3] - b[1]) >= MIN_SIZE]
    for b in boxes:
        if b in big:
            continue
        for t in big:
            if t[0] - MARGIN <= b[0] and b[2] <= t[2] + MARGIN and t[1] - MARGIN <= b[1] and b[3] <= t[3] + MARGIN:
                t[0], t[1], t[2], t[3] = min(t[0], b[0]), min(t[1], b[1]), max(t[2], b[2]), max(t[3], b[3])
    big.sort(key=lambda b: ((b[1] + b[3]) // 2 // 100, b[0]))         # rows of about 100 px, then left to right
    return big


def save_crop(img: pygame.Surface, box, name: str) -> None:
    rect = pygame.Rect(box[0], box[1], box[2] - box[0] + 1, box[3] - box[1] + 1)
    OUT.mkdir(parents=True, exist_ok=True)
    pygame.image.save(img.subsurface(rect).copy(), str(OUT / f"{name}.png"))
    print(f"saved {name}.png  ({rect.w}x{rect.h})")


def main(argv) -> None:
    if len(argv) < 2:
        print(__doc__)
        return
    pygame.init()
    sheet = pygame.image.load(argv[1])
    found = characters(sheet)
    if len(found) != len(NAMES):
        print(f"warning: found {len(found)} figures but expected {len(NAMES)}; names may be off")
    for box, name in zip(found, NAMES):
        save_crop(sheet, box, name)
    if len(argv) > 2:                                                  # single-figure image, e.g. the Mind Flayer
        extra = pygame.image.load(argv[2])
        save_crop(extra, [0, 0, extra.get_width() - 1, extra.get_height() - 1], "mind_flayer")


if __name__ == "__main__":
    main(sys.argv)