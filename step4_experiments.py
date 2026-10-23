"""
Шаг 4. Эксперименты для исследования.

  Эксперимент 1. «Экзамен без книги»: нейросеть отвечает на 50 вопросов по памяти.
  Эксперимент 2. «Поиск нужной страницы»: сравниваем три способа поиска карточек.
  Эксперимент 3. «Экзамен с открытой книгой»: нейросеть отвечает, подглядывая в библиотеку (RAG).

Ответы проверяются автоматически: ответ засчитывается, если в нём есть
ключевое слово из правильного ответа (например, «1923» или «Гребнев»).

Запуск:
  python step4_experiments.py search    — только эксперимент 2 (быстро)
  python step4_experiments.py answers   — эксперименты 1 и 3 (долго: нейросеть отвечает 200 раз)
  python step4_experiments.py report    — таблицы и графики по уже готовым результатам
  python step4_experiments.py           — всё по очереди
  добавьте --quick, чтобы взять 15 вопросов и одну модель (около 10 минут)
"""
import csv
import json
import re
import sys
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import requests

from config import CHARTS_DIR, MODELS_FOR_EXPERIMENT, OLLAMA_URL, QUESTIONS_FILE, RESULTS_DIR, TOP_K
from rag import Library, answer

ANSWERS_FILE = RESULTS_DIR / "answers.csv"
SEARCH_FILE = RESULTS_DIR / "search.csv"

# Фразы, по которым видно, что нейросеть честно призналась, что не знает
REFUSALS = ["не знаю", "нет ответа", "нет информации", "нет данных", "нет сведений",
            "не могу ответить", "не упоминается", "не указан", "не содержит", "не могу сказать"]

RESULT_NAMES = {"correct": "Верно", "refusal": "«Не знаю»", "wrong": "Ошибка (выдумка)"}
MODE_NAMES = {"memory": "без библиотеки", "rag": "с библиотекой"}


def normalize(text):
    """Маленькие буквы, «ё» → «е», знаки препинания → пробелы."""
    text = text.lower().replace("ё", "е")
    return " " + re.sub(r"[^а-яa-z0-9-]+", " ", text) + " "


def grade(reply, question):
    """Проверяет ответ: correct — верно, refusal — «не знаю», wrong — ошибка."""
    text = normalize(reply)
    refused = any(r in text for r in REFUSALS)
    has_keyword = any(k in text for k in question["keywords"])
    if question.get("trap"):
        # В вопросе-ловушке верно — не поддаться обману (сказать «нет» или «не знаю»)
        return "correct" if (has_keyword or refused) else "wrong"
    if has_keyword:
        return "correct"
    return "refusal" if refused else "wrong"


# Быстрый режим (--quick): 15 вопросов и одна модель — когда мало времени
QUICK_IDS = {1, 3, 5, 7, 15, 20, 22, 23, 30, 33, 36, 42, 46, 48, 50}
QUICK = "--quick" in sys.argv
MODELS = MODELS_FOR_EXPERIMENT[:1] if QUICK else MODELS_FOR_EXPERIMENT


def load_questions():
    questions = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
    return [q for q in questions if q["id"] in QUICK_IDS] if QUICK else questions


# ---------- Эксперимент 2: поиск ----------

def run_search_experiment():
    library = Library()
    questions = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
    questions = [q for q in questions if not q.get("trap")]
    rows = []
    for method, method_name in Library.METHODS.items():
        for k in (1, 3, 5):
            found = 0
            for q in questions:
                cards = library.search(q["question"], k=k, method=method)
                cards_text = normalize(" ".join(f"{c['source']} {c['section']} {c['text']}" for c in cards))
                if any(word in cards_text for word in q["keywords"]):
                    found += 1
            percent = round(100 * found / len(questions))
            rows.append({"method": method, "method_name": method_name, "k": k,
                         "found": found, "total": len(questions), "percent": percent})
            print(f"{method_name:32} k={k}: нашёл ответ для {found}/{len(questions)} ({percent}%)")
    write_csv(SEARCH_FILE, rows)


# ---------- Эксперименты 1 и 3: ответы нейросети ----------

def unload(model):
    """Выгружает модель из памяти, чтобы следующей хватило оперативной памяти."""
    requests.post(OLLAMA_URL.replace("/api/chat", "/api/generate"),
                  json={"model": model, "keep_alive": 0}, timeout=60)


def run_answer_experiments():
    library = Library()
    questions = load_questions()
    done = set()
    if ANSWERS_FILE.exists():  # продолжаем с того места, где остановились
        with open(ANSWERS_FILE, encoding="utf-8-sig") as f:
            done = {(r["model"], r["mode"], r["id"]) for r in csv.DictReader(f)}

    fields = ["model", "mode", "id", "topic", "question", "expected", "reply", "result", "seconds", "sources"]
    new_file = not ANSWERS_FILE.exists()
    with open(ANSWERS_FILE, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if new_file:
            writer.writeheader()
        for model in MODELS:
            for mode in ("memory", "rag"):
                for q in questions:
                    if (model, mode, str(q["id"])) in done:
                        continue
                    start = time.time()
                    reply, cards = answer(q["question"], library if mode == "rag" else None, model, TOP_K)
                    seconds = round(time.time() - start, 1)
                    result = grade(reply, q)
                    writer.writerow({
                        "model": model, "mode": mode, "id": q["id"], "topic": q["topic"],
                        "question": q["question"], "expected": q["answer"], "reply": reply,
                        "result": result, "seconds": seconds,
                        "sources": " | ".join(f"{c['source']} — {c['section']}" for c in cards),
                    })
                    f.flush()
                    print(f"[{model} / {MODE_NAMES[mode]}] №{q['id']} {RESULT_NAMES[result]} ({seconds} с)")
            unload(model)


# ---------- Отчёт: таблицы и графики ----------

INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
METHOD_COLORS = {"words": "#2a78d6", "stems": "#eb6834", "bm25": "#1baf7a"}
RESULT_COLORS = {"correct": "#0ca30c", "refusal": "#b9b8b3", "wrong": "#d03b3b"}


def style_axes(ax):
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(colors=MUTED, length=0)
    ax.set_axisbelow(True)


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def chart_search():
    rows = read_csv(SEARCH_FILE)
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=200)
    width = 0.26
    for i, (method, name) in enumerate(Library.METHODS.items()):
        values = [int(r["percent"]) for r in rows if r["method"] == method]
        xs = [x + (i - 1) * (width + 0.02) for x in range(3)]
        bars = ax.bar(xs, values, width, color=METHOD_COLORS[method], label=name)
        for bar, v in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, v + 1.5, f"{v}%",
                    ha="center", fontsize=9, color=INK)
    ax.set_xticks(range(3), ["1 карточка", "3 карточки", "5 карточек"])
    ax.set_ylim(0, 110)
    ax.set_ylabel("Вопросов, для которых найден ответ, %", color=MUTED)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_yticks(range(0, 101, 20))
    style_axes(ax)
    ax.legend(frameon=False, loc="upper left", ncol=3, fontsize=9)
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / "chart_search.png")
    plt.close(fig)


def summarize_answers(rows):
    """Считает верные / «не знаю» / ошибки для каждой модели и режима."""
    summary = []
    for model in MODELS:
        for mode in ("memory", "rag"):
            part = [r for r in rows if r["model"] == model and r["mode"] == mode]
            if not part:
                continue
            facts = [r for r in part if r["topic"] != "Ловушка"]
            traps = [r for r in part if r["topic"] == "Ловушка"]
            item = {"model": model, "mode": mode, "facts": len(facts)}
            for key in RESULT_NAMES:
                item[key] = sum(r["result"] == key for r in facts)
            item["traps_ok"] = sum(r["result"] == "correct" for r in traps)
            item["traps"] = len(traps)
            item["avg_seconds"] = round(sum(float(r["seconds"]) for r in part) / len(part), 1)
            summary.append(item)
    return summary


def chart_answers(summary):
    labels = [f"{s['model']}\n{MODE_NAMES[s['mode']]}" for s in summary]
    fig, ax = plt.subplots(figsize=(8, 0.9 * len(summary) + 1.2), dpi=200)
    lefts = [0] * len(summary)
    for key, name in RESULT_NAMES.items():
        values = [100 * s[key] / s["facts"] for s in summary]
        ax.barh(range(len(summary)), values, left=lefts, color=RESULT_COLORS[key],
                label=name, height=0.6, edgecolor="white", linewidth=2)
        for y, (left, v) in enumerate(zip(lefts, values)):
            if v >= 7:
                ax.text(left + v / 2, y, f"{v:.0f}%", ha="center", va="center",
                        fontsize=9, color="white" if key != "refusal" else INK)
        lefts = [l + v for l, v in zip(lefts, values)]
    ax.set_yticks(range(len(summary)), labels, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel(f"Доля ответов на {summary[0]['facts']} фактических вопросов, %", color=MUTED)
    style_axes(ax)
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3, fontsize=9)
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / "chart_answers.png")
    plt.close(fig)


def chart_topics(rows):
    """Доля верных ответов по темам: без библиотеки и с библиотекой (обе модели вместе)."""
    topics = ["Биография", "Награды", "Журавли", "Произведения", "Память"]
    fig, ax = plt.subplots(figsize=(8, 4), dpi=200)
    width = 0.38
    for i, (mode, color) in enumerate((("memory", "#86b6ef"), ("rag", "#1c5cab"))):
        values = []
        for t in topics:
            part = [r for r in rows if r["topic"] == t and r["mode"] == mode]
            values.append(round(100 * sum(r["result"] == "correct" for r in part) / len(part)) if part else 0)
        xs = [x + (i - 0.5) * (width + 0.02) for x in range(len(topics))]
        bars = ax.bar(xs, values, width, color=color, label=MODE_NAMES[mode].capitalize())
        for bar, v in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, v + 1.5, f"{v}%", ha="center", fontsize=9, color=INK)
    ax.set_xticks(range(len(topics)), topics)
    ax.set_ylim(0, 110)
    ax.set_yticks(range(0, 101, 20))
    ax.set_ylabel("Верных ответов, %", color=MUTED)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    style_axes(ax)
    ax.legend(frameon=False, loc="upper left", ncol=2, fontsize=9)
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / "chart_topics.png")
    plt.close(fig)


def make_report():
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    if SEARCH_FILE.exists():
        chart_search()
    if ANSWERS_FILE.exists():
        ids = {str(q["id"]) for q in load_questions()}
        rows = [r for r in read_csv(ANSWERS_FILE) if r["id"] in ids and r["model"] in MODELS]
        summary = summarize_answers(rows)
        write_csv(RESULTS_DIR / "summary.csv", summary)
        chart_answers(summary)
        chart_topics(rows)
        for s in summary:
            print(f"{s['model']:14} {MODE_NAMES[s['mode']]:16} верно {s['correct']}/{s['facts']}, "
                  f"«не знаю» {s['refusal']}, ошибки {s['wrong']}, ловушки {s['traps_ok']}/{s['traps']}, "
                  f"в среднем {s['avg_seconds']} с на ответ")
    print(f"Графики сохранены в папку {CHARTS_DIR}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    step = args[0] if args else "all"
    if step in ("search", "all"):
        run_search_experiment()
    if step in ("answers", "all"):
        run_answer_experiments()
    if step in ("report", "all"):
        make_report()
