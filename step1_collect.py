"""
Шаг 1. Сбор данных («собираем библиотеку»).

Программа по очереди скачивает страницы о Расуле Гамзатове и его произведениях
из Википедии и Викицитатника, «вытаскивает» из HTML-кода абзацы, списки
и таблицы (это и называется парсингом), убирает служебные разделы
и сохраняет результат как обычные текстовые файлы в папку data/raw.

Запуск:  python step1_collect.py
"""
import json
import re
import time

import requests
from bs4 import BeautifulSoup

from config import RAW_DIR, SOURCES

HEADERS = {"User-Agent": "GamzatovRAG/1.0 (school research project)"}

# Разделы, в которых нет полезного текста (списки ссылок, примечания и т.п.)
SKIP_SECTIONS = {
    "примечания", "литература", "ссылки", "см. также", "источники",
    "комментарии", "сноски", "галерея",
}

# Служебные элементы страницы, которые выбрасываем до разбора
JUNK = ["sup.reference", ".mw-editsection", ".navbox", ".reflist", ".references",
        ".noprint", ".metadata", ".mw-empty-elt", "style", "script", "figure", ".thumb"]


def download_html(site, title):
    """Скачивает HTML-код статьи через API сайта."""
    params = {"action": "parse", "page": title, "prop": "text",
              "redirects": 1, "format": "json", "formatversion": 2}
    for attempt in range(5):
        response = requests.get(f"https://{site}/w/api.php", params=params,
                                headers=HEADERS, timeout=30)
        if response.status_code != 429:
            break
        # Сайт просит подождать («слишком много запросов») — ждём и пробуем снова
        wait = int(response.headers.get("retry-after", 30))
        print(f"    сайт просит подождать {wait} с...")
        time.sleep(wait + 1)
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        return None
    return data["parse"]["text"]


def text_of(element):
    """Текст элемента без лишних пробелов."""
    text = element.get_text(" ", strip=True)
    text = re.sub(r"\s+([.,;:!?»)])", r"\1", text)  # «слово ,» → «слово,»
    text = re.sub(r"([«(])\s+", r"\1", text)
    return re.sub(r"\s{2,}", " ", text)


def html_to_lines(element):
    """Обходит страницу сверху вниз и превращает её в строки текста."""
    lines = []
    for el in element.find_all(recursive=False):
        classes = el.get("class") or []
        if el.name in ("h2", "h3", "h4") or "mw-heading" in classes:
            heading = el if el.name in ("h2", "h3", "h4") else el.find(["h2", "h3", "h4"])
            level = int(heading.name[1])
            lines.append(f"{'=' * level} {text_of(heading)} {'=' * level}")
        elif el.name in ("p", "blockquote"):
            lines.append(text_of(el))
        elif el.name in ("ul", "ol"):
            lines += ["— " + text_of(li) for li in el.find_all("li", recursive=False)]
        elif el.name == "dl":
            lines += [text_of(item) for item in el.find_all(["dt", "dd"])]
        elif el.name == "table":
            # Каждая строка таблицы → «ячейка: ячейка | ячейка»
            for row in el.find_all("tr"):
                cells = [text_of(c) for c in row.find_all(["th", "td"], recursive=False)]
                cells = [c for c in cells if c]
                if len(cells) >= 2:
                    lines.append(f"{cells[0]}: {' | '.join(cells[1:])}")
                elif cells:
                    lines.append(cells[0])
        elif el.name == "div":
            lines += html_to_lines(el)  # заходим внутрь блоков-обёрток
    return [line for line in lines if line.strip("— ")]


def parse_article(html):
    """Из HTML-кода получает чистый текст статьи."""
    soup = BeautifulSoup(html, "html.parser")
    for junk in soup.select(", ".join(JUNK)):
        junk.decompose()
    root = soup.select_one(".mw-parser-output") or soup

    # Выбрасываем служебные разделы (и все их подразделы)
    result, skip_level = [], None
    for line in html_to_lines(root):
        heading = re.fullmatch(r"(=+) (.+) =+", line)
        if heading:
            level = len(heading.group(1))
            if skip_level is not None and level > skip_level:
                continue
            skip_level = level if heading.group(2).lower() in SKIP_SECTIONS else None
        if skip_level is None:
            result.append(line)
    return "\n".join(result)


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    catalog = []
    for number, (site, title) in enumerate(SOURCES, start=1):
        html = download_html(site, title)
        if not html:
            print(f"[!] Не найдено: {title}")
            continue
        text = parse_article(html)
        url = f"https://{site}/wiki/{title.replace(' ', '_')}"
        safe_title = re.sub(r"[^\w]+", "_", title).strip("_")
        file_name = f"{number:02d}_{safe_title}.txt"
        (RAW_DIR / file_name).write_text(f"{title}\n{url}\n\n{text}", encoding="utf-8")
        catalog.append({"file": file_name, "title": title, "url": url, "chars": len(text)})
        print(f"[ok] {title}: {len(text)} символов")
        time.sleep(3)  # вежливая пауза, чтобы не нагружать сайт

    (RAW_DIR.parent / "sources.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(item["chars"] for item in catalog)
    print(f"\nГотово: {len(catalog)} статей, всего {total} символов.")


if __name__ == "__main__":
    main()
