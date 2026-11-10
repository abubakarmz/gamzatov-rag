"""
Веб-версия помощника (для показа на защите).

Запуск:  streamlit run app.py
Откроется страница в браузере. Переключатель «Подглядывать в библиотеку»
позволяет прямо на защите показать разницу: нейросеть «по памяти» и с RAG.
"""
import streamlit as st

from config import MODEL
from rag import Library, answer

st.set_page_config(page_title="Помощник по Гамзатову", page_icon="🕊️")
st.title("🕊️ Помощник по творчеству Расула Гамзатова")
st.caption("Отвечает на вопросы, опираясь на собранную библиотеку статей.")


@st.cache_resource
def get_library():
    return Library()


library = get_library()
with st.sidebar:
    model = MODEL  # qwen2.5:1.5b — маленькая модель, хватает ноутбука с 8 ГБ памяти
    use_library = st.toggle("Подглядывать в библиотеку (RAG)", value=True)
    # Без библиотеки по умолчанию задаём просто вопрос, как обычному чат-боту
    allow_unknown = st.toggle("Разрешить ответ «Я не знаю»", value=False, disabled=use_library)
    st.write(f"Карточек в библиотеке: {len(library.chunks)}")

if "history" not in st.session_state:
    st.session_state.history = []

for role, text in st.session_state.history:
    st.chat_message(role).markdown(text)

question = st.chat_input("Например: кто написал музыку к песне «Журавли»?")
if question:
    st.chat_message("user").markdown(question)
    with st.spinner("Ищу в библиотеке и думаю..."):
        reply, cards = answer(question, library if use_library else None, model, allow_unknown=allow_unknown)
    if cards:
        reply += "\n\n**Источники:**\n" + "\n".join(
            f"- [{c['source']} — {c['section']}]({c['url']})" for c in cards)
    elif not use_library:
        reply += "\n\n*Ответ «по памяти», без библиотеки — может быть выдумкой.*"
    st.chat_message("assistant").markdown(reply)
    st.session_state.history += [("user", question), ("assistant", reply)]
