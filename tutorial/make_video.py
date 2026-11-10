"""
Собирает обучающее видео: слайды + озвучка (голос Microsoft Svetlana через edge-tts) + субтитры.
Результат: docs/Видео_как_работает_проект.mp4

Запуск:  python make_video.py
"""
import asyncio
import hashlib
import re
import subprocess
import sys
from pathlib import Path

import edge_tts
import imageio_ffmpeg

from draw import Slide
from script import ROOT, SLIDES

VOICE = "ru-RU-SvetlanaNeural"
RATE = "-4%"
BUILD = Path(__file__).parent / "build"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
OUT = ROOT / "docs" / "Видео_как_работает_проект.mp4"
PAUSE = 0.45  # пауза после каждой фразы, секунд

# Как произносить слова, которые голос читает неправильно
SAY = [
    ("streamlit run app.py", "стримлит ран эпп точка пай"), ("ollama pull", "оллама пул"),
    ("pip install", "пип инстолл"), ("Retrieval-Augmented Generation", "ретривал огментед дженерейшн"),
    ("ChatGPT", "Чат Джи Пи Ти"), ("BM25", "Бэ Эм двадцать пять"), ("HTML", "эйч ти эм эль"),
    ("Python", "Пайтон"), ("Ollama", "Оллама"), ("Qwen", "Квен"), ("Llama", "Лама"),
    ("Snowball", "Сноубол"), ("RAG", "Раг"), ("make_docs", "мейк докс"), ("config", "конфиг"),
    ("step1", "степ один"), ("step2", "степ два"), ("step3", "степ три"), ("step4", "степ четыре"),
    ("Файл rag", "Файл раг"), ("файл rag", "файл раг"), ("и app", "и эпп"), ("«.py»", "«точка пай»"),
    ("«p»", "«пэ»"), ("«a»", "«а»"), ("«b»", "«бэ»"),
]


def speech(text):
    for a, b in SAY:
        text = text.replace(a, b)
    return text


def sentences(text):
    parts = re.split(r"(?<=[.!?…])\s+(?=[А-ЯЁA-Z«„\"])", text)
    # слишком короткие фразы приклеиваем к следующей
    out = []
    for p in parts:
        if out and len(out[-1]) < 40:
            out[-1] += " " + p
        else:
            out.append(p)
    return out


def audio_path(sent):
    key = hashlib.md5(f"{VOICE}{RATE}{speech(sent)}".encode()).hexdigest()[:12]
    return key, BUILD / "audio" / f"{key}.mp3"


async def tts(text, path, limit):
    if path.exists() and path.stat().st_size > 0:
        return
    async with limit:
        for attempt in range(6):
            try:
                await asyncio.wait_for(edge_tts.Communicate(speech(text), VOICE, rate=RATE).save(str(path)), 90)
                if path.stat().st_size > 0:
                    return
            except Exception as e:  # сеть может моргнуть — пробуем ещё раз
                print("  повтор озвучки:", type(e).__name__)
            await asyncio.sleep(2 + attempt * 2)
    raise RuntimeError(f"Не удалось озвучить: {text}")


async def voice_all(all_sentences):
    """Озвучивает все фразы сразу, по 6 одновременно."""
    limit = asyncio.Semaphore(6)
    await asyncio.gather(*(tts(s, audio_path(s)[1], limit) for s in all_sentences))


def duration(path):
    err = subprocess.run([FFMPEG, "-i", str(path)], capture_output=True, text=True, encoding="utf-8", errors="ignore").stderr
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def main():
    for d in ("audio", "frames", "clips"):
        (BUILD / d).mkdir(parents=True, exist_ok=True)
    all_sentences = [s for _, beats in SLIDES for beat in beats for s in sentences(beat)]
    print(f"Озвучиваю {len(all_sentences)} фраз...")
    asyncio.run(voice_all(all_sentences))
    clips = []
    total = 0.0
    for n, (fn, beats) in enumerate(SLIDES, 1):
        for b, beat in enumerate(beats):
            slide = Slide()
            fn(slide, b)
            for k, sent in enumerate(sentences(beat)):
                key, audio = audio_path(sent)
                frame = BUILD / "frames" / f"{n:02d}_{b:02d}_{k:02d}.png"
                slide.with_subtitle(sent).save(frame)
                clip = BUILD / "clips" / f"{n:02d}_{b:02d}_{k:02d}_{key}.mp4"
                dur = duration(audio) + PAUSE
                if not clip.exists():
                    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-loop", "1", "-framerate", "25", "-i", str(frame),
                                    "-i", str(audio), "-af", f"apad=pad_dur={PAUSE}", "-t", f"{dur:.3f}",
                                    "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-pix_fmt", "yuv420p",
                                    "-r", "25", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", str(clip)], check=True)
                clips.append(clip)
                total += dur
        print(f"слайд {n}/{len(SLIDES)} готов, всего {total / 60:.1f} мин")

    # Удаляем клипы, которые остались от старых версий сценария
    keep = set(clips)
    for old in (BUILD / "clips").glob("*.mp4"):
        if old not in keep:
            old.unlink()
    listing = BUILD / "clips.txt"
    listing.write_text("".join(f"file '{c.as_posix()}'\n" for c in clips), encoding="utf-8")
    OUT.parent.mkdir(exist_ok=True)
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                    "-c", "copy", "-movflags", "+faststart", str(OUT)], check=True)
    print(f"Видео готово: {OUT} ({total / 60:.1f} мин)")


if __name__ == "__main__":
    sys.exit(main())
