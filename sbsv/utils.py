ESCAPE_MAP = {
    "\b": "\\b",
    "\t": "\\t",
    "\n": "\\n",
    "\f": "\\f",
    "\r": "\\r",
    '"': '\\"',
    "/": "\\/",
    "\\": "\\\\",
    "[": "\\[",
    "]": "\\]",
    ",": "\\,",
    ":": "\\:",
}


def get_schema_id(*args) -> str:
    return "$".join(args)


def get_schema_name_list(schema: str) -> list:
    return schema.split("$")


def escape_str(s: str) -> str:
    escaped_str = s
    for raw, escaped in ESCAPE_MAP.items():
        escaped_str = escaped_str.replace(raw, escaped)
    return escaped_str


def unescape_str(s: str) -> str:
    unescaped_str = s
    for raw, escaped in ESCAPE_MAP.items():
        unescaped_str = unescaped_str.replace(escaped, raw)
    return unescaped_str
