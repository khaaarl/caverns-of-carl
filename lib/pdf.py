import os

from lib.utils import COC_ROOT_DIR, CharStyle, StyledString


LOADED_PDFLAB = False

try:
    import reportlab.lib.pagesizes
    from reportlab.pdfbase.pdfmetrics import stringWidth
    import reportlab.pdfgen.canvas

    LOADED_PDFLAB = True
except:
    print("Failed to import reportlab.")


def produce_pdf_if_possible(df, name):
    if LOADED_PDFLAB:
        return produce_pdf(df, name)
    return None


def font_normal():
    return "Courier"


def font_bold():
    return "Courier-Bold"


def max_rows(font_size):
    return int((11 * 72 - 2 * _DOC_PAGE_MARGIN) / font_size)


def max_cols(font_char_width):
    return int((8.5 * 72 - 2 * _DOC_PAGE_MARGIN) / font_char_width)


_FONT_SIZE = 20
_FONT_CHAR_WIDTH = 12
_DOC_PAGE_MARGIN = int(72 / 2)
_DOC_PAGE_TOP = 11 * 72 - _DOC_PAGE_MARGIN
_DOC_PAGE_LEFT = _DOC_PAGE_MARGIN
_DOC_PAGE_MAX_ROWS = max_rows(_FONT_SIZE)
_DOC_PAGE_MAX_COLS = max_cols(_FONT_CHAR_WIDTH)


def draw_pagenum(canvas, pagenum):
    canvas.setFont(font_normal(), _FONT_SIZE)
    canvas.setFillColorRGB(0, 0, 0)
    canvas.setStrokeColorRGB(0, 0, 0)
    canvas.drawRightString(
        int(8.5 * 72 - _DOC_PAGE_MARGIN / 2),
        int(_DOC_PAGE_MARGIN / 2),
        str(pagenum),
    )


class Page:
    def __init__(self, pagenum, lines=[]):
        self.pagenum = pagenum
        self.lines = list(lines)

    def bookmark_names(self):
        bookmark_names = set()
        for line in self.lines:
            for c in line.chars:
                if c.bookmark_name is not None:
                    bookmark_names.add(c.bookmark_name)
        return bookmark_names

    def render(self, canvas, accumulated_bookmark_names=set()):
        canvas.setFont(font_normal(), _FONT_SIZE)
        for lineix, line in enumerate(self.lines):
            y = int(_DOC_PAGE_TOP - (lineix + 0.5) * _FONT_SIZE)
            line = StyledString(line)
            for c in line.chars:
                if c.link_destination and not c.style:
                    c.style = CharStyle(0, 32, 64)
            groups = line.split_by_style()
            rowix = 0
            for group in groups:
                x = _DOC_PAGE_LEFT + rowix * _FONT_CHAR_WIDTH
                s = "".join([c.c for c in group.chars])
                style = group.chars[0].style
                if style:
                    # set the style for the background box
                    canvas.setFillColorRGB(0, 0, 0)
                    canvas.setStrokeColorRGB(0, 0, 0)
                    w = len(s) * _FONT_CHAR_WIDTH
                    h = _FONT_SIZE
                    # TODO: figure out a more elegant y offset
                    dy = int(_FONT_SIZE / 5)
                    if not group.chars[0].link_destination:
                        canvas.rect(x, y - dy, w, h, stroke=0, fill=1)
                    # now set style for the text
                    if style.is_bold:
                        canvas.setFont(font_bold(), _FONT_SIZE)
                    else:
                        canvas.setFont(font_normal(), _FONT_SIZE)
                    canvas.setFillColorRGB(style.r, style.g, style.b)
                    canvas.setStrokeColorRGB(style.r, style.g, style.b)
                else:
                    canvas.setFont(font_normal(), _FONT_SIZE)
                    canvas.setFillColorRGB(0, 0, 0)
                    canvas.setStrokeColorRGB(0, 0, 0)
                canvas.drawString(x, y, s)
                rowix += len(s)
            # Add bookmarks
            for c in line.chars:
                if c.bookmark_name is None:
                    continue
                if c.bookmark_name in accumulated_bookmark_names:
                    continue
                by = y + _FONT_SIZE
                canvas.bookmarkHorizontalAbsolute(c.bookmark_name, by)
                accumulated_bookmark_names.add(c.bookmark_name)
            # Add outgoing links
            cur_link = None
            cur_link_start = 0
            cur_link_end = 0
            for ix in range(len(line.chars) + 1):
                new_link = None
                if ix < len(line.chars):
                    new_link = line.chars[ix].link_destination
                if new_link == cur_link:
                    cur_link_end = ix + 1
                    continue
                if cur_link is not None:
                    x1 = _DOC_PAGE_LEFT + cur_link_start * _FONT_CHAR_WIDTH
                    x2 = _DOC_PAGE_LEFT + cur_link_end * _FONT_CHAR_WIDTH
                    # TODO: figure out a more elegant y offset
                    dy = int(_FONT_SIZE / 5)
                    y1 = y - dy
                    y2 = y1 + _FONT_SIZE
                    canvas.linkAbsolute("", cur_link, Rect=(x1, y1, x2, y2))
                cur_link_start = ix
                cur_link_end = ix + 1
                cur_link = new_link

        # Page number in the corner
        draw_pagenum(canvas, self.pagenum)
        canvas.showPage()


def docs_to_pages(docs, start_page_num):
    pages = [Page(pagenum=start_page_num)]
    for doc in docs:
        s = doc.flat_str(separator="\n\n")
        linel = []
        for line in s.split("\n"):
            wordl = []
            line_len = 0
            num_appends = 0
            for word in line.split(" "):
                wordlen = len(word.chars)
                if (
                    line_len != 0
                    and line_len + 1 + wordlen > _DOC_PAGE_MAX_COLS
                ):
                    linel.append(wordl)
                    wordl = []
                    line_len = 0
                    num_appends += 1
                line_len += 1 + wordlen
                wordl.append(word)
            if num_appends == 0 or line_len != 0:
                linel.append(wordl)
        if (
            pages[-1].lines
            and len(pages[-1].lines) + len(linel) + 1 > _DOC_PAGE_MAX_ROWS
        ):
            pages.append(Page(pagenum=pages[-1].pagenum + 1))
        if pages[-1].lines:
            pages[-1].lines.append(StyledString(""))
        for wordl in linel:
            if len(pages[-1].lines) >= _DOC_PAGE_MAX_ROWS:
                pages.append(Page(pagenum=pages[-1].pagenum + 1))
            pages[-1].lines.append(StyledString(" ").join(wordl))
    if not pages[-1].lines:
        pages.pop()
    return pages


def draw_map_page(canvas, df, pagenum):
    sizes = [(20, 12), (15, 9), (10, 6), (5, 3)]
    chosen_size, chosen_width = 5, 3
    while (df.height <= max_rows(chosen_size + 5)) and (
        df.width <= max_cols(chosen_width + 3)
    ):
        chosen_size += 5
        chosen_width += 3
    num_rows = max_rows(chosen_size)
    num_cols = max_cols(chosen_width)

    # background box
    canvas.setFillColorRGB(0, 0, 0)
    canvas.setStrokeColorRGB(0, 0, 0)
    w = chosen_width * df.width
    h = chosen_size * df.height
    # TODO: figure out a more elegant y offset
    dy = int(chosen_size / 5)
    y = _DOC_PAGE_TOP - (df.height - 0.5) * chosen_size - dy
    canvas.rect(_DOC_PAGE_LEFT, y, w, h, stroke=0, fill=1)
    s = StyledString(df.ascii(colors=True))
    lines = s.split("\n")
    for lineix, line in enumerate(lines):
        y = int(_DOC_PAGE_TOP - (lineix + 0.5) * chosen_size)
        for ix, c in enumerate(line.chars):
            if lineix >= num_rows or ix >= num_cols:
                continue
            x = _DOC_PAGE_LEFT + ix * chosen_width
            style = c.style
            if not style:
                style = CharStyle(255, 255, 255)
            # now set style for the text
            if style.is_bold:
                canvas.setFont(font_bold(), chosen_size)
            else:
                canvas.setFont(font_normal(), chosen_size)
            canvas.setFillColorRGB(style.r, style.g, style.b)
            canvas.setStrokeColorRGB(style.r, style.g, style.b)
            canvas.drawString(x, y, c.c)
    draw_pagenum(canvas, pagenum)
    canvas.showPage()


def produce_pdf(df, name):
    assert stringWidth("m", font_normal(), _FONT_SIZE) == _FONT_CHAR_WIDTH
    assert stringWidth("m", font_bold(), _FONT_SIZE) == _FONT_CHAR_WIDTH
    pdf_dir = os.path.join(COC_ROOT_DIR, "output", "pdfs")
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_filename = os.path.join(pdf_dir, f"{name}.pdf")
    canvas = reportlab.pdfgen.canvas.Canvas(
        pdf_filename, pagesize=reportlab.lib.pagesizes.letter
    )
    docs = []
    for room in df.rooms:
        docs.append(room.description(df, verbose=True))
    for corridor in sorted(df.corridors, key=lambda x: x.name or ""):
        if not corridor.is_nontrivial(df):
            continue
        docs.append(corridor.description(df, verbose=True))
    draw_map_page(canvas, df, 1)
    accumulated_bookmark_names = set()
    for page in docs_to_pages(docs, 2):
        page.render(
            canvas, accumulated_bookmark_names=accumulated_bookmark_names
        )
    canvas.save()
    return pdf_filename
