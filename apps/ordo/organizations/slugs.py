from django.utils.text import slugify


CYRILLIC_TO_LATIN = str.maketrans(
    {
        "а": "a",
        "ә": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "ғ": "gh",
        "д": "d",
        "е": "e",
        "ё": "e",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "і": "i",
        "й": "i",
        "к": "k",
        "қ": "q",
        "л": "l",
        "м": "m",
        "н": "n",
        "ң": "n",
        "о": "o",
        "ө": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ұ": "u",
        "ү": "u",
        "ф": "f",
        "х": "kh",
        "һ": "h",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "shch",
        "ъ": "",
        "ы": "y",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
    }
)

RESERVED_ROOT_SLUGS = frozenset(
    {"accounts", "admin", "media", "new-workspace", "static", "workspaces"}
)


def ascii_slugify(value, *, fallback="item"):
    transliterated = str(value).strip().casefold().translate(CYRILLIC_TO_LATIN)
    return slugify(transliterated, allow_unicode=False) or fallback


def unreserved_root_slug(value, *, fallback="item", suffix="workspace"):
    slug = ascii_slugify(value, fallback=fallback)
    return f"{slug}-{suffix}" if slug in RESERVED_ROOT_SLUGS else slug
