"""
Превращает файлы .md из этой папки в PDF.
Если поменяли текст в .md (например, вписали имя и школу) — просто запустите снова.

Запуск:  python защита/make_pdf.py
"""
import re
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (HRFlowable, ListFlowable, ListItem, Paragraph, Preformatted,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

HERE = Path(__file__).parent
FONTS = "C:/Windows/Fonts/"
for name, file in [("ARL", "arial.ttf"), ("ARL-B", "arialbd.ttf"), ("ARL-I", "ariali.ttf"),
                   ("ARL-BI", "arialbi.ttf"), ("MONO", "consola.ttf")]:
    pdfmetrics.registerFont(TTFont(name, FONTS + file))
pdfmetrics.registerFontFamily("ARL", normal="ARL", bold="ARL-B", italic="ARL-I", boldItalic="ARL-BI")

BLUE, BLUE_BG, GREY, LINE = HexColor("#1c5cab"), HexColor("#eef4fc"), HexColor("#52514e"), HexColor("#b9b8b3")


def make_styles(size):
    base = ParagraphStyle("p", fontName="ARL", fontSize=size, leading=size * 1.45, spaceAfter=size * 0.5)
    return {
        "p": base,
        "h1": ParagraphStyle("h1", parent=base, fontName="ARL-B", fontSize=size + 7, leading=(size + 7) * 1.25,
                             textColor=BLUE, spaceBefore=6, spaceAfter=12),
        "h2": ParagraphStyle("h2", parent=base, fontName="ARL-B", fontSize=size + 3, leading=(size + 3) * 1.3,
                             textColor=BLUE, spaceBefore=14, spaceAfter=6, keepWithNext=True),
        "h3": ParagraphStyle("h3", parent=base, fontName="ARL-B", fontSize=size + 1, leading=(size + 1) * 1.35,
                             spaceBefore=10, spaceAfter=4, keepWithNext=True),
        "h4": ParagraphStyle("h4", parent=base, fontName="ARL-B", spaceBefore=8, keepWithNext=True),
        "note": ParagraphStyle("note", parent=base, fontSize=size - 1, textColor=GREY, backColor=BLUE_BG,
                               borderPadding=7, leftIndent=7, rightIndent=7, spaceBefore=6, spaceAfter=12),
        "cell": ParagraphStyle("cell", parent=base, fontSize=size - 2, leading=(size - 2) * 1.35, spaceAfter=0),
        "code": ParagraphStyle("code", fontName="MONO", fontSize=size - 3, leading=(size - 3) * 1.35,
                               backColor=HexColor("#f4f4f2"), borderPadding=6, leftIndent=6,
                               spaceBefore=4, spaceAfter=10),
    }


def inline(text):
    """Markdown внутри строки (**жирный**, *курсив*, `код`) → разметка reportlab."""
    text = re.sub(r"[\U00010000-\U0010FFFF]", "", text)  # эмодзи шрифт не умеет рисовать
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"`([^`]+)`", r'<font name="MONO" color="#1c5cab">\1</font>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", text)
    # Подсказки для выступающего [Слайд 3] — синим, чтобы не читать их вслух
    text = re.sub(r"(<b>)?(\[(?:Слайд|Показать|Задать|Выключить|Ответить|Открыть)[^\]]*\])(</b>)?",
                  r'<font color="#1c5cab"><b>\2</b></font>', text)
    return text


def make_table(rows, st, width):
    rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    rows = [r for r in rows if not all(re.fullmatch(r":?-+:?", c) for c in r)]
    data = [[Paragraph(inline(c), st["cell"]) for c in r] for r in rows]
    t = Table(data, colWidths=[width / len(rows[0])] * len(rows[0]), repeatRows=1)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, LINE), ("BACKGROUND", (0, 0), (-1, 0), BLUE_BG),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    return [t, Spacer(1, 8)]


def make_list(items, st, numbered):
    flow = [ListItem(Paragraph(inline(i), st["p"]), leftIndent=18) for i in items]
    return [ListFlowable(flow, bulletType="1" if numbered else "bullet", start=1 if numbered else None, bulletFormat="%s." if numbered else None,
                         leftIndent=18, bulletFontName="ARL", bulletFontSize=st["p"].fontSize - 1)]


def md_to_story(md, st, width):
    story, lines, i = [], md.splitlines(), 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            j = i + 1
            while not lines[j].startswith("```"):
                j += 1
            story.append(Preformatted("\n".join(lines[i + 1:j]), st["code"]))
            i = j + 1
        elif re.fullmatch(r"-{3,}", line.strip()):
            # Подряд идущие «---» дают одну линию
            if not story or not isinstance(story[-1], HRFlowable):
                story.append(HRFlowable(width="100%", color=LINE, thickness=0.6, spaceBefore=6, spaceAfter=10))
            i += 1
        elif m := re.match(r"(#{1,4}) (.*)", line):
            story.append(Paragraph(inline(m.group(2)), st[f"h{len(m.group(1))}"]))
            i += 1
        elif line.startswith(">"):
            block = []
            while i < len(lines) and lines[i].startswith(">"):
                block.append(lines[i].lstrip("> ").strip())
                i += 1
            story.append(Paragraph("<br/>".join(inline(b) for b in block), st["note"]))
        elif line.startswith("|"):
            block = []
            while i < len(lines) and lines[i].startswith("|"):
                block.append(lines[i])
                i += 1
            story += make_table(block, st, width)
        elif re.match(r"\s*(- |\d+\. )", line):
            numbered = bool(re.match(r"\s*\d+\. ", line))
            items = []
            while i < len(lines) and re.match(r"\s*(- |\d+\. )", lines[i]):
                items.append(re.sub(r"^\s*(- |\d+\. )", "", lines[i]))
                i += 1
            story += make_list(items, st, numbered)
        elif line.strip():
            block = []
            while i < len(lines) and lines[i].strip() and not re.match(r"(#|>|\||```|\s*- |\s*\d+\. |-{3,})", lines[i]):
                block.append(lines[i].strip())
                i += 1
            story.append(Paragraph(inline(" ".join(block)), st["p"]))
        else:
            i += 1
    return story


def page_number(canvas, doc):
    canvas.setFont("ARL", 9)
    canvas.setFillColor(GREY)
    canvas.drawCentredString(A4[0] / 2, 1.1 * cm, str(doc.page))


def build(md_file, size):
    margin = 2 * cm
    width = A4[0] - 2 * margin
    st = make_styles(size)
    pdf = md_file.with_suffix(".pdf")
    SimpleDocTemplate(str(pdf), pagesize=A4, leftMargin=margin, rightMargin=margin,
                      topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                      title=md_file.stem.split("_", 1)[1].replace("_", " ")).build(
        md_to_story(md_file.read_text(encoding="utf-8"), st, width),
        onFirstPage=page_number, onLaterPages=page_number)
    print(f"Готово: {pdf.name}")


if __name__ == "__main__":
    # Текст выступления — крупнее, чтобы удобно читать с листа
    build(HERE / "1_Текст_выступления_и_вопросы_жюри.md", size=13)
    build(HERE / "2_Объяснение_кода.md", size=11)
    build(HERE / "3_Текст_к_презентации.md", size=13)
