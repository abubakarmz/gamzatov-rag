"""Рисует последнее состояние каждого слайда в tutorial/build/preview (для проверки и для PDF)."""
from pathlib import Path

from draw import Slide
from script import SLIDES

OUT = Path(__file__).parent / "build" / "preview"

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for n, (fn, beats) in enumerate(SLIDES, 1):
        s = Slide()
        fn(s, len(beats) - 1)
        s.img.crop((0, 0, 1920, 880)).save(OUT / f"slide_{n:02d}.png")
    print(f"{len(SLIDES)} слайдов, {sum(len(b) for _, b in SLIDES)} реплик")
