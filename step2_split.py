"""
Шаг 2. Нарезка текстов на «карточки».

Нейросеть не может прочитать сразу всю библиотеку, поэтому каждая статья
делится на небольшие кусочки (карточки) примерно по CHUNK_SIZE символов.
Каждая карточка помнит, из какой статьи и какого раздела она взята.

Запуск:  python step2_split.py
"""
import json
import re

from config import CHUNK_SIZE, CHUNKS_FILE, RAW_DIR


def split_into_sentences(paragraph):
    return re.split(r"(?<=[.!?…])\s+", paragraph)


def make_chunks(text, size):
    """Складывает абзацы в карточки, пока карточка не станет длиннее size."""
    pieces = []
    for paragraph in text.split("\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        # Слишком длинный абзац режем по предложениям
        pieces.extend(split_into_sentences(paragraph) if len(paragraph) > size else [paragraph])

    chunks, current = [], ""
    for piece in pieces:
        if current and len(current) + len(piece) > size:
            chunks.append(current)
            current = ""
        current = f"{current}\n{piece}" if current else piece
    if current:
        chunks.append(current)
    return chunks


def main():
    all_chunks = []
    for path in sorted(RAW_DIR.glob("*.txt")):
        title, url, _, *lines = path.read_text(encoding="utf-8").split("\n")
        text = "\n".join(lines)

        # Делим статью на разделы, чтобы карточка знала свой раздел
        parts = re.split(r"\n=+ ([^=\n]+) =+\n", "\n" + text)
        sections = [("Начало статьи", parts[0])] + list(zip(parts[1::2], parts[2::2]))

        for section, body in sections:
            for chunk in make_chunks(body, CHUNK_SIZE):
                all_chunks.append({
                    "id": len(all_chunks),
                    "source": title,
                    "section": section.strip(),
                    "url": url,
                    "text": chunk,
                })

    CHUNKS_FILE.write_text(json.dumps(all_chunks, ensure_ascii=False, indent=1), encoding="utf-8")
    sizes = [len(c["text"]) for c in all_chunks]
    print(f"Готово: {len(all_chunks)} карточек, средняя длина {sum(sizes) // len(sizes)} символов.")


if __name__ == "__main__":
    main()
