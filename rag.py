"""
Сердце проекта: «библиотекарь» (поиск карточек) и «рассказчик» (нейросеть).

RAG (Retrieval-Augmented Generation) — «генерация с подглядыванием в источники»:
  1) по вопросу находим несколько подходящих карточек из библиотеки;
  2) отдаём их нейросети вместе с вопросом;
  3) нейросеть отвечает, опираясь только на эти карточки.
"""
import json
import math
import re
from collections import Counter

import requests
from snowballstemmer import stemmer

from config import CHUNKS_FILE, MODEL, OLLAMA_URL, TOP_K

# Частые слова, которые ничего не говорят о смысле вопроса
STOP_WORDS = set("""
а без более бы был была были было быть в вам вас весь во вот все всего всех вы
где да даже для до его ее ей ему если есть еще же за и из или им их к как какая
какие каким каких какой какое какую когда кого кто ли между мне можно мы на над
не него нее нет ни них но ну о об однако он она они оно от по под при про с со
так также такой там те тем то того тоже только том ты у уже хотя чего чей чем
что чтобы чье эта эти это этого этой этом этот я году год сколько каком какую
""".split())

_stemmer = stemmer("russian")


def words_of(text):
    """Разбивает текст на слова: маленькие буквы, «ё» → «е», без стоп-слов."""
    words = re.findall(r"[а-яёa-z0-9]+", text.lower().replace("ё", "е"))
    return [w for w in words if w not in STOP_WORDS]


def stems_of(text):
    """То же, но каждое слово обрезано до основы: «журавлях» → «журавл»."""
    return [_stemmer.stemWord(w) for w in words_of(text)]


class Library:
    """Библиотека карточек и три способа поиска по ней."""

    METHODS = {
        "words": "Совпадение слов",
        "stems": "Совпадение основ слов",
        "bm25": "BM25 (основы + редкость слов)",
    }

    def __init__(self, chunks_file=CHUNKS_FILE):
        self.chunks = json.loads(chunks_file.read_text(encoding="utf-8"))
        # Ищем не только по тексту, но и по названию статьи и раздела
        full = [f"{c['source']}. {c['section']}. {c['text']}" for c in self.chunks]
        self.word_sets = [set(words_of(t)) for t in full]
        self.stem_lists = [stems_of(t) for t in full]
        self.stem_sets = [set(s) for s in self.stem_lists]

        # Подготовка для BM25: сколько карточек содержит каждую основу
        n = len(self.chunks)
        doc_freq = Counter(stem for stems in self.stem_sets for stem in stems)
        self.idf = {s: math.log(1 + (n - df + 0.5) / (df + 0.5)) for s, df in doc_freq.items()}
        self.counts = [Counter(s) for s in self.stem_lists]
        self.avg_len = sum(len(s) for s in self.stem_lists) / n

    def _score(self, question, method):
        if method == "words":
            # Способ 1: сколько слов вопроса встречается в карточке (точно, буква в букву)
            q = set(words_of(question))
            return [len(q & ws) for ws in self.word_sets]
        if method == "stems":
            # Способ 2: то же, но сравниваем основы слов («Гамзатова» = «Гамзатову»)
            q = set(stems_of(question))
            return [len(q & ss) for ss in self.stem_sets]
        if method == "bm25":
            # Способ 3: BM25 — редкие слова важнее частых,
            # а длинная карточка не получает преимущества только за длину
            k1, b = 1.5, 0.75
            q = set(stems_of(question))
            scores = []
            for counts, stems in zip(self.counts, self.stem_lists):
                norm = k1 * (1 - b + b * len(stems) / self.avg_len)
                scores.append(sum(
                    self.idf.get(s, 0) * counts[s] * (k1 + 1) / (counts[s] + norm)
                    for s in q if s in counts))
            return scores
        raise ValueError(f"Неизвестный способ поиска: {method}")

    def search(self, question, k=TOP_K, method="bm25"):
        """Возвращает k самых подходящих карточек."""
        scores = self._score(question, method)
        best = sorted(range(len(scores)), key=lambda i: -scores[i])[:k]
        return [self.chunks[i] for i in best if scores[i] > 0]


SYSTEM_PROMPT = (
    "Ты — помощник школьника по творчеству Расула Гамзатова. "
    "Отвечай по-русски, коротко: 1–3 предложения."
)

PROMPT_NO_LIBRARY = (
    "Вопрос: {question}\n"
    "Если ты не знаешь точного ответа, так и скажи: «Я не знаю»."
)

PROMPT_WITH_LIBRARY = (
    "Ниже даны фрагменты из библиотеки. Ответь на вопрос, используя ТОЛЬКО эти фрагменты.\n"
    "Если в них нет ответа, скажи: «В моей библиотеке нет ответа».\n\n"
    "{fragments}\n\n"
    "Вопрос: {question}"
)


def ask_model(prompt, model=MODEL):
    """Отправляет запрос нейросети, запущенной в Ollama, и возвращает её ответ."""
    response = requests.post(OLLAMA_URL, json={
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        # temperature = 0: на один и тот же вопрос модель отвечает одинаково
        "options": {"temperature": 0, "num_predict": 200, "num_ctx": 4096},
    }, timeout=900)
    response.raise_for_status()
    return response.json()["message"]["content"].strip()


def answer(question, library=None, model=MODEL, k=TOP_K):
    """Отвечает на вопрос. Если library=None — нейросеть отвечает «по памяти»."""
    if library is None:
        return ask_model(PROMPT_NO_LIBRARY.format(question=question), model), []
    found = library.search(question, k=k)
    fragments = "\n\n".join(
        f"[{i}] {c['source']} — {c['section']}:\n{c['text']}" for i, c in enumerate(found, 1))
    prompt = PROMPT_WITH_LIBRARY.format(fragments=fragments, question=question)
    return ask_model(prompt, model), found
