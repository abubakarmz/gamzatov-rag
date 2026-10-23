# Настройки проекта. Всё, что можно поменять, собрано в одном месте.
from pathlib import Path

# Папки проекта
ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw"            # сюда сохраняются скачанные статьи
CHUNKS_FILE = ROOT / "data" / "chunks.json"  # «карточки» — кусочки текста
QUESTIONS_FILE = ROOT / "research" / "questions.json"
RESULTS_DIR = ROOT / "research" / "results"
CHARTS_DIR = ROOT / "research" / "charts"

# Откуда берём тексты: (сайт, название статьи).
# Это открытые источники со свободной лицензией CC BY-SA.
SOURCES = [
    ("ru.wikipedia.org", "Гамзатов, Расул Гамзатович"),
    ("ru.wikiquote.org", "Расул Гамзатович Гамзатов"),
    ("ru.wikipedia.org", "Журавли (песня)"),
    ("ru.wikipedia.org", "Мой Дагестан (книга)"),
    ("ru.wikipedia.org", "Горянка (поэма)"),
    ("ru.wikipedia.org", "Горянка (фильм)"),
    ("ru.wikipedia.org", "Сказание о Хочбаре"),
    ("ru.wikipedia.org", "Хочбар (опера)"),
    ("ru.wikipedia.org", "Пожелание (песня)"),
    ("ru.wikipedia.org", "Цадаса, Гамзат"),
    ("ru.wikipedia.org", "Цада"),
    ("ru.wikipedia.org", "Белые журавли (памятник)"),
    ("ru.wikipedia.org", "Белые журавли (музей)"),
    ("ru.wikipedia.org", "Гамзатов, Гаджи Гамзатович"),
    ("ru.wikipedia.org", "Гамзатова, Патимат Расуловна"),
    ("ru.wikipedia.org", "Дагестанский музей изобразительных искусств имени П. С. Гамзатовой"),
    ("ru.wikipedia.org", "Гребнев, Наум Исаевич"),
    ("ru.wikipedia.org", "Козловский, Яков Абрамович"),
    ("ru.wikipedia.org", "Аварская литература"),
    ("ru.wikipedia.org", "Дагестанская литература"),
]

# Нарезка текста на карточки
CHUNK_SIZE = 700  # примерная длина одной карточки в символах

# Поиск
TOP_K = 3  # сколько карточек отдавать нейросети

# Нейросеть (запускается локально через программу Ollama)
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen2.5:1.5b"
MODELS_FOR_EXPERIMENT = ["qwen2.5:1.5b", "llama3.2:3b"]
