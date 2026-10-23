"""
Шаг 3. Задаём вопросы помощнику в консоли.

Запуск:  python step3_ask.py
Чтобы выйти, введите пустую строку.
"""
from config import MODEL
from rag import Library, answer


def main():
    library = Library()
    print(f"Помощник по творчеству Расула Гамзатова (модель {MODEL}).")
    print(f"В библиотеке {len(library.chunks)} карточек. Пустая строка — выход.\n")
    while True:
        question = input("Ваш вопрос: ").strip()
        if not question:
            break
        reply, cards = answer(question, library)
        print(f"\nОтвет: {reply}\n")
        print("Источники:")
        for card in cards:
            print(f"  • {card['source']} — {card['section']}  ({card['url']})")
        print()


if __name__ == "__main__":
    main()
