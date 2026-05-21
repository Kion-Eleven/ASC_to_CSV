#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Convert resource/icon.png to resource/icon.ico for Windows builds."""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PNG_PATH = os.path.join(ROOT, "resource", "icon.png")
ICO_PATH = os.path.join(ROOT, "resource", "icon.ico")


def main() -> int:
    if not os.path.isfile(PNG_PATH):
        print(f"[INFO] Skip icon conversion: {PNG_PATH} not found")
        return 0

    try:
        from PIL import Image
    except ImportError:
        print("[INFO] Pillow not installed; skip icon conversion")
        return 0

    os.makedirs(os.path.dirname(ICO_PATH), exist_ok=True)
    img = Image.open(PNG_PATH)
    if img.mode not in ("RGBA", "RGB"):
        img = img.convert("RGBA")
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(ICO_PATH, format="ICO", sizes=sizes)
    print(f"[OK] Wrote {ICO_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
