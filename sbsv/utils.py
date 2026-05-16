ESCAPE_MAP = {
    "\b": "\\b",
    "\t": "\\t",
    "\n": "\\n",
    "\f": "\\f",
    "\r": "\\r",
    '"': '\\"',
    "\\": "\\\\",
    "[": "\\[",
    "]": "\\]",
}

UNESCAPE_MAP = {escaped[1]: raw for raw, escaped in ESCAPE_MAP.items()}


def get_schema_id(*args) -> str:
    return "$".join(args)


def get_schema_name_list(schema: str) -> list:
    return schema.split("$")


def _escape_char(c: str, quote: bool) -> str:
    if c in ["[", "]"] and quote:
        return c
    if c in ESCAPE_MAP:
        return ESCAPE_MAP[c]
    return c


def _escape_unquoted_brackets(chars: list) -> set:
    escaped = set()
    stack = list()
    for i, c in enumerate(chars):
        if c == "[":
            stack.append(i)
        elif c == "]":
            if len(stack) == 0:
                escaped.add(i)
            else:
                stack.pop()
    escaped.update(stack)
    return escaped


def escape_str(s: str, quote: bool = False) -> str:
    if quote:
        return '"' + "".join(_escape_char(c, quote=True) for c in s) + '"'

    chars = list(s)
    escaped_brackets = _escape_unquoted_brackets(chars)
    result = list()
    for i, c in enumerate(chars):
        if i in escaped_brackets:
            result.append("\\" + c)
        elif c in ["[", "]"]:
            result.append(c)
        else:
            result.append(_escape_char(c, quote=False))
    return "".join(result)


def _is_valid_quoted(s: str) -> bool:
    escape = False
    for c in s[1:-1]:
        if escape:
            if c not in UNESCAPE_MAP:
                raise ValueError(f"Invalid escape sequence: \\{c}")
            escape = False
            continue
        if c == "\\":
            escape = True
            continue
        if c == '"':
            raise ValueError("Invalid quoted string: unescaped quote")
    if escape:
        raise ValueError("Invalid quoted string: trailing escape")
    return not escape


def unescape_str(s: str) -> str:
    strict = False
    stripped = s.strip()
    if stripped.startswith('"'):
        if len(stripped) < 2 or not stripped.endswith('"'):
            raise ValueError("Invalid quoted string: unterminated quote")
        _is_valid_quoted(stripped)
        s = stripped[1:-1]
        strict = True
    result = list()
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            escaped = s[i + 1]
            if escaped in UNESCAPE_MAP:
                result.append(UNESCAPE_MAP[escaped])
                i += 2
                continue
            if strict:
                raise ValueError(f"Invalid escape sequence: \\{escaped}")
        elif s[i] == "\\" and strict:
            raise ValueError("Invalid quoted string: trailing escape")
        result.append(s[i])
        i += 1
    return "".join(result)
