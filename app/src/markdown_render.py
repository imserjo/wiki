import bleach
import markdown as md


ALLOWED_TAGS = [
    "p", "br", "hr",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "strong", "b", "em", "i", "u", "s", "del", "ins",
    "ul", "ol", "li",
    "blockquote", "pre", "code",
    "a", "img",
    "table", "thead", "tbody", "tr", "th", "td",
    "span", "div",
]

ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "rel", "target"],
    "img": ["src", "alt", "title", "width", "height"],
    "code": ["class"],
    "pre": ["class"],
    "span": ["class"],          # ← Pygments добавляет <span class="k">, <span class="s"> и т.д.
    "div": ["class"],           # ← <div class="codehilite">
}

ALLOWED_PROTOCOLS = ["http", "https", "mailto"]


def render_markdown(text: str) -> str:
    if not text:
        return ""

    html = md.markdown(
        text,
        extensions=[
            "fenced_code",
            "tables",
            "nl2br",
            "sane_lists",
            "toc",
            "codehilite",          # ← НОВОЕ: подсветка синтаксиса
        ],
        extension_configs={
            "toc": {"permalink": False},
            "codehilite": {
                "guess_lang": False,     # не угадывать язык, если не указан
                "css_class": "codehilite",
                "linenums": False,       # без номеров строк (можно True)
            },
        },
    )

    clean = bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )

    clean = bleach.linkify(clean, skip_tags=["pre", "code"])
    return clean