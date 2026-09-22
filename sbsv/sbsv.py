import enum
import heapq
import re
from operator import attrgetter
from typing import Any, Callable, Dict, List, Optional, Set, TextIO, Tuple

from .utils import unescape_str

try:
    from . import _native
except ImportError:
    _native = None


def native_available() -> bool:
    return _native is not None


NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
BUILTIN_TYPES = frozenset(("str", "int", "float", "bool", "null", "hex"))


def validate_name(name: str, context: str):
    if NAME_PATTERN.match(name) is None:
        raise ValueError(f"Invalid {context} name '{name}': use only [A-Za-z0-9_-]")


class TokenType(enum.Enum):
    LEFT_BRACKET = 1
    RIGHT_BRACKET = 2
    COLON = 3
    COMMA = 4
    STRING = 5
    NUMBER = 6
    BOOLEAN = 7
    NULL = 8
    IDENTIFIER = 9
    EOL = 10


class lexer:
    def __init__(self):
        pass

    @staticmethod
    def update_token(result: List[str], current: List[str]):
        token = "".join(current).strip()
        if token:
            result.append(token)

    @staticmethod
    def can_start_quote(current: List[str], nonspace_count: int) -> bool:
        if nonspace_count == 0:
            return True
        return bool(current) and current[-1].isspace() and nonspace_count == 1

    @staticmethod
    def tokenize(line: str, strict: bool = False) -> List[str]:
        result: List[str] = []
        level = 0
        current: List[str] = []
        escape = False
        quote = False
        nonspace_count = 0

        for char in line:
            if escape:
                escape = False
                if level > 0:
                    current.append("\\")
                    current.append(char)
                    if not char.isspace():
                        nonspace_count += 1
                continue

            if char == "\\" and level > 0:
                escape = True
                continue

            if (
                char == '"'
                and level > 0
                and (quote or lexer.can_start_quote(current, nonspace_count))
            ):
                quote = not quote
                current.append(char)
                nonspace_count += 1
                continue

            if char == "[" and not quote:
                level += 1
                if level == 1:
                    if current:
                        lexer.update_token(result, current)
                    current = []
                    nonspace_count = 0
                    continue
            elif char == "]" and not quote:
                level -= 1
                if level < 0:
                    if strict:
                        raise ValueError("Invalid data: unmatched closing bracket")
                    level = 0
                    continue
                if level == 0:
                    lexer.update_token(result, current)
                    current = []
                    nonspace_count = 0
                    continue

            if level > 0:
                current.append(char)
                if not char.isspace():
                    nonspace_count += 1

        if escape and level > 0:
            current.append("\\")
            nonspace_count += 1
        if strict and quote:
            raise ValueError("Invalid data: unterminated quoted string")
        if strict and level > 0:
            raise ValueError("Invalid data: unterminated bracket")
        if strict and level < 0:
            raise ValueError("Invalid data: unmatched closing bracket")
        return result

    @staticmethod
    def token_key_and_has_value(token: str) -> Tuple[str, bool]:
        stripped = token.strip()
        if stripped == "":
            return "", False
        parts = stripped.split(None, maxsplit=1)
        return parts[0], len(parts) > 1

    @staticmethod
    def token_split(token: str, delimiter: Optional[str]) -> Tuple[str, str]:
        tokens = token.split(delimiter, maxsplit=1)
        if len(tokens) == 0:
            return "", ""
        if len(tokens) == 1:
            return unescape_str(tokens[0].strip()), ""
        return unescape_str(tokens[0].strip()), tokens[1].strip()

    @staticmethod
    def token_split_default(token: str) -> Tuple[str, str]:
        return lexer.token_split(token, None)

    @staticmethod
    def token_split_schema(token: str) -> Tuple[str, str]:
        return lexer.token_split(token, ":")


class SbsvData(dict):
    __slots__ = ("schema_name", "id")

    schema_name: str
    id: int

    def __init__(
        self,
        schema_name: str,
        data: Optional[Dict[str, Any]] = None,
        id: int = -1,
    ):
        super().__init__(data or {})
        self.schema_name = schema_name
        self.id = id

    @property
    def data(self) -> "SbsvData":
        return self

    def __str__(self) -> str:
        return (
            f"[schema {self.schema_name}] [id {self.id}] "
            f"[data {dict.__repr__(self)}]"
        )

    def __repr__(self) -> str:
        return f"SbsvData({self.__str__()})"

    def get_id(self) -> int:
        return self.id

    def set_id(self, id: int):
        self.id = id

    def get_name(self) -> str:
        return self.schema_name


class SbsvDataType:
    name: str
    name_with_tag: str
    type: str
    nullable: bool
    converter: Callable[[str], Any]
    is_list: bool
    sub_type: List["SbsvDataType"]

    def __init__(
        self,
        name_with_tag: str,
        type: str,
        custom_types: Optional[Dict[str, Callable[[str], Any]]] = None,
    ):
        self.nullable = name_with_tag.endswith("?")
        if self.nullable:
            name_with_tag = name_with_tag[:-1]
        self.name_with_tag = name_with_tag
        if "$" in self.name_with_tag:
            tokens = self.name_with_tag.split("$")
            for token in tokens:
                validate_name(token, "schema field")
            self.name = tokens[0]
        else:
            validate_name(name_with_tag, "schema field")
            self.name = name_with_tag
        self.type = type
        self.is_list = SbsvDataType.list_sub_type(type) is not None
        self.converter = self.add_converter(type, custom_types or dict())
        self.sub_type = list()

    @staticmethod
    def to_bool(value: str) -> bool:
        value = value.strip().lower()
        if value in ["t", "true", "y", "yes", "1"]:
            return True
        elif value in ["f", "false", "n", "no", "0"]:
            return False
        raise ValueError(f"Invalid boolean value: {value}")

    @staticmethod
    def to_null(value: str) -> None:
        if value.strip().lower() == "null":
            return None
        raise ValueError(f"Invalid null value: {value}")

    @staticmethod
    def list_sub_type(type: str) -> Optional[str]:
        if not type.startswith("list"):
            return None
        if not type.startswith("list[") or not type.endswith("]"):
            raise ValueError(f"Invalid list type: {type}")
        sub_type = type[5:-1]
        if sub_type == "":
            raise ValueError(f"Invalid list type: {type}")
        return sub_type

    def add_converter(
        self, type: str, custom_types: Dict[str, Callable[[str], Any]]
    ) -> Callable[[str], Any]:
        # Primitive types
        if type == "int":
            return int
        if type == "float":
            return float
        if type == "str":
            return str
        if type == "bool":
            return SbsvDataType.to_bool
        if type == "null":
            return SbsvDataType.to_null
        if type == "hex":
            return lambda value: int(value, 16)
        # Complex types
        sub_type = SbsvDataType.list_sub_type(type)
        if sub_type is not None:
            sub_converter = SbsvDataType(sub_type, sub_type, custom_types)
            return lambda x: [
                sub_converter.convert(v) for v in lexer.tokenize(x, strict=True)
            ]
        # Custom types
        if type in custom_types:
            return custom_types[type]
        # Unsupported types
        raise ValueError(f"Unsupported type: {type}")

    def convert(self, value: str) -> Any:
        if value == "" and self.nullable:
            return None
        if not self.is_list:
            value = unescape_str(value)
        return self.converter(value)

    def key(self) -> str:
        return self.name_with_tag

    def check_nullable(self) -> bool:
        return self.nullable

    def check_name(self, name: str) -> bool:
        return self.name == name


class SchemaBody:
    original: str
    schema: List[SbsvDataType]

    def __init__(
        self,
        schema_body: Optional[str] = None,
        tokens: Optional[List[str]] = None,
        custom_types: Optional[Dict[str, Callable[[str], Any]]] = None,
    ):
        if schema_body is None and tokens is None:
            raise ValueError("schema_body or tokens is required")
        self.schema = list()
        if custom_types is None:
            custom_types = dict()
        if tokens is None:
            if schema_body is None:
                raise ValueError("schema_body or tokens is required")
            tokens = lexer.tokenize(schema_body, strict=True)
        self.original = (
            schema_body if schema_body is not None else SchemaBody.format_tokens(tokens)
        )
        for token in tokens:
            self.schema.append(self.parse_schema_token(token, custom_types))

    @staticmethod
    def format_tokens(tokens: List[str]) -> str:
        return " ".join([f"[{token}]" for token in tokens])

    @staticmethod
    def parse_schema_token(
        token: str, custom_types: Dict[str, Callable[[str], Any]]
    ) -> SbsvDataType:
        key, value = lexer.token_split_schema(token)
        if key == "":
            raise ValueError(f"Invalid schema token [{token}]: empty name")
        if value == "":
            raise ValueError(f"Invalid schema token [{token}]: missing type annotation")
        return SbsvDataType(key, value, custom_types)

    def parse(self, tokens: List[str]) -> Dict[str, Any]:
        result = dict()
        if len(tokens) < len(self.schema):
            raise ValueError(
                "Invalid data: expected at least "
                f"{len(self.schema)} fields, got {len(tokens)} "
                f"in {SchemaBody.format_tokens(tokens)}"
            )

        start = 0
        for schema_type in self.schema:
            done = False
            while start < len(tokens):
                elem = tokens[start]
                start += 1
                key, value = lexer.token_split_default(elem)
                if key == "":
                    raise ValueError(f"Invalid data token [{elem}]: empty name")
                if schema_type.name != key:
                    continue
                if value == "" and not schema_type.nullable:
                    raise ValueError(
                        f"Invalid data token [{elem}]: empty value for "
                        f"non-nullable key '{schema_type.name}'"
                    )
                try:
                    result[schema_type.name_with_tag] = schema_type.convert(value)
                except Exception as e:
                    raise ValueError(
                        f"Invalid value for key '{schema_type.name}' "
                        f"as type '{schema_type.type}': {value!r}"
                    ) from e
                done = True
                break
            if not done:
                raise ValueError(
                    f"Invalid data: missing key '{schema_type.name}' "
                    f"in {SchemaBody.format_tokens(tokens)}"
                )

        return result


class Schema:
    original: str
    name: str
    schema: List[SbsvDataType]
    body: SchemaBody
    data: List[SbsvData]

    def __init__(
        self,
        s: str,
        custom_types: Optional[Dict[str, Callable[[str], Any]]] = None,
    ):
        self.original = s
        self.name = ""
        self.schema = list()
        self.data = list()
        tokens = lexer.tokenize(s, strict=True)
        if len(tokens) == 0:
            raise ValueError(f"Invalid schema {s}: too short")
        self.name = tokens[0]
        validate_name(self.name, "schema")
        body_tokens = list()
        body_started = False
        for i in range(1, len(tokens)):
            token = tokens[i]
            key, value = lexer.token_split_default(token)
            if key == "":
                raise ValueError(f"Invalid schema token [{token}]: empty name")
            if ":" in token:
                body_started = True
                body_tokens.append(token)
                continue
            if not body_started and value == "":
                validate_name(key, "sub-schema")
                self.name = f"{self.name}${key}"
                continue
            raise ValueError(f"Invalid schema token [{token}]: missing type annotation")
        self.body = SchemaBody(tokens=body_tokens, custom_types=custom_types)
        self.schema = self.body.schema
        if len(self.schema) > 0 and self.schema[0].check_nullable():
            raise ValueError(
                f"Invalid schema {s}: first body field "
                f"'{self.schema[0].name_with_tag}' cannot be nullable"
            )

    @staticmethod
    def need_parsing(s: str) -> bool:
        return s.startswith("[") and s.endswith("]")

    @staticmethod
    def preprocess(line: str) -> Tuple[Optional[str], List[str]]:
        tokens = lexer.tokenize(line, strict=True)
        return Schema.extract_schema_and_body_tokens(tokens)

    @staticmethod
    def extract_schema_and_body_tokens(
        tokens: List[str],
    ) -> Tuple[Optional[str], List[str]]:
        parts = []
        for i, token in enumerate(tokens):
            key, has_value = lexer.token_key_and_has_value(token)
            if not key or has_value:
                # Once the body starts, subsequent tokens cannot be schema names.
                return "$".join(parts) if parts else None, tokens[i:]
            parts.append(key)
        return "$".join(parts) if parts else None, []

    def parse(self, tokens: List[str]) -> Dict[str, Any]:
        return self.body.parse(tokens)

    def get_data(self) -> List[SbsvData]:
        return self.data

    def append_data(self, data: SbsvData):
        self.data.append(data)


class IgnorePrefix:
    original: str
    tokens: List[Tuple[str, Optional[SbsvDataType]]]
    save_ignored: bool

    def __init__(
        self,
        prefix: str,
        save_ignored: bool = False,
        custom_types: Optional[Dict[str, Callable[[str], Any]]] = None,
    ):
        self.original = prefix
        tokens = lexer.tokenize(prefix, strict=True)
        if len(tokens) == 0:
            raise ValueError(f"Invalid ignore prefix {prefix}: too short")
        self.tokens = list()
        self.save_ignored = save_ignored
        if custom_types is None:
            custom_types = dict()
        for token in tokens:
            key, value = lexer.token_split_schema(token)
            if key == "":
                raise ValueError(f"Invalid ignore prefix token [{token}]: empty name")
            if not key.startswith("$"):
                self.tokens.append((key, None))
                continue
            validate_name(key[1:], "ignored prefix")
            if value == "":
                value = "str"
            schema_type = SbsvDataType(key[1:], value, custom_types)
            schema_type.name_with_tag = key
            schema_type.name = key
            self.tokens.append((key, schema_type))

    def parse_tokens(self, tokens: List[str]) -> Tuple[List[str], Dict[str, Any]]:
        if len(tokens) < len(self.tokens):
            raise ValueError(
                "Invalid data: expected at least "
                f"{len(self.tokens)} ignored prefix fields, got {len(tokens)} "
                f"in {SchemaBody.format_tokens(tokens)}"
            )
        ignored = dict()
        for i in range(len(self.tokens)):
            expected, schema_type = self.tokens[i]
            actual = tokens[i]
            if schema_type is None:
                if actual != expected:
                    raise ValueError(
                        f"Invalid ignored prefix token [{actual}]: "
                        f"expected [{expected}]"
                    )
                continue
            if self.save_ignored:
                try:
                    ignored[schema_type.key()] = schema_type.convert(actual)
                except Exception as e:
                    raise ValueError(
                        f"Invalid ignored prefix value for key '{schema_type.name}' "
                        f"as type '{schema_type.type}': {actual!r}"
                    ) from e
        return tokens[len(self.tokens) :], ignored


class body_parser:
    body: SchemaBody
    custom_types: Dict[str, Callable[[str], Any]]

    def __init__(
        self,
        schema_body: str,
        custom_types: Optional[Dict[str, Callable[[str], Any]]] = None,
    ):
        self.custom_types = dict(custom_types or dict())
        self.body = SchemaBody(schema_body, custom_types=self.custom_types)

    def loads(self, s: str) -> Dict[str, Any]:
        return self.parse_tokens(lexer.tokenize(s, strict=True))

    def parse_tokens(self, tokens: List[str]) -> Dict[str, Any]:
        return self.body.parse(tokens)

    def add_custom_type(self, type_name: str, type_function: Callable[[str], Any]):
        self.custom_types[type_name] = type_function
        return self


class parser:
    schema: Dict[str, Schema]
    schema_prefixes: Set[str]
    ignore_unknown: bool
    ignored_prefix: Optional[IgnorePrefix]
    schema_roots: Set[str]
    custom_types: Dict[str, Callable[[str], Any]]
    data: List[SbsvData]
    groups: Dict[str, Tuple[Schema, Schema, List[Tuple[int, int]]]]
    group_start: Dict[str, int]
    group_end: Dict[str, str]
    result: dict

    def __init__(self, ignore_unknown: bool = True, use_native: bool = True):
        self.schema = dict()
        self.schema_prefixes = set()
        self.ignore_unknown = ignore_unknown
        self.use_native = use_native
        self.schema_roots = set()
        self.ignored_prefix = None
        self.custom_types = dict()
        self.data = list()
        self.result = dict()
        self.groups = dict()
        self.group_start = dict()
        self.group_end = dict()
        self._native_backend = None

    # New parser with the same configuration and independent result state.
    def clone(self) -> "parser":
        result = parser(self.ignore_unknown, self.use_native)
        for type_name, converter in self.custom_types.items():
            result.add_custom_type(type_name, converter)
        if self.ignored_prefix is not None:
            result.ignore_prefix(
                self.ignored_prefix.original,
                self.ignored_prefix.save_ignored,
            )
        for schema in self.schema.values():
            result.add_schema(schema.original)
        for group_name, (start_schema, end_schema, _) in self.groups.items():
            result.add_group(group_name, start_schema.name, end_schema.name)
        return result

    @staticmethod
    def _build_parse_error_message(
        original_error: Exception,
        line_number: Optional[int] = None,
        schema_name: Optional[str] = None,
        line: Optional[str] = None,
    ) -> str:
        error_message = str(original_error)
        context = list()
        if line_number is not None:
            context.append(f"line={line_number}")
        if schema_name is not None:
            context.append(f"schema={schema_name}")
        if line is not None:
            context.append(f"input={line!r}")
        if len(context) == 0:
            return error_message
        return f"Parse error ({', '.join(context)}): {error_message}"

    def get_global_id(self) -> int:
        return len(self.data)

    def match_schema(
        self, name: Optional[str], line_number: Optional[int] = None
    ) -> Optional[Schema]:
        if name not in self.schema:
            if self.ignore_unknown:
                return None
            schema_name = name if name is not None else "<missing>"
            raise ValueError(f"Unknown schema '{schema_name}'")
        return self.schema[name]

    @staticmethod
    def _token_has_value(token: str) -> bool:
        return lexer.token_key_and_has_value(token)[1]

    def _schema_name_may_match(
        self, schema_name: Optional[str], ambiguous_sub_schema: bool
    ) -> bool:
        if schema_name is None:
            return False
        if schema_name in self.schema:
            return True
        if not ambiguous_sub_schema:
            return False
        return schema_name in self.schema_prefixes

    def _has_unknown_schema_root(self, line: str) -> bool:
        if self.ignored_prefix is not None:
            return False
        start = 0
        line_length = len(line)
        while start < line_length and line[start].isspace():
            start += 1
        if start == line_length or line[start] != "[":
            return False
        end = line.find("]", start + 1)
        if end < 0:
            return False
        key, has_value = lexer.token_key_and_has_value(line[start + 1 : end])
        return key == "" or has_value or key not in self.schema_roots

    def _extract_schema_name_fast(self, line: str) -> Tuple[Optional[str], bool, bool]:
        ignored = self.ignored_prefix
        ignored_prefix_len = 0 if ignored is None else len(ignored.tokens)

        token_index = 0
        schema_parts: List[str] = []
        level = 0
        current: List[str] = []
        escape = False
        quote = False
        nonspace_count = 0

        for char in line:
            if escape:
                escape = False
                if level > 0:
                    current.append("\\")
                    current.append(char)
                    if not char.isspace():
                        nonspace_count += 1
                continue

            if char == "\\" and level > 0:
                escape = True
                continue

            if (
                char == '"'
                and level > 0
                and (quote or lexer.can_start_quote(current, nonspace_count))
            ):
                quote = not quote
                current.append(char)
                nonspace_count += 1
                continue

            if char == "[" and not quote:
                level += 1
                if level == 1:
                    current = []
                    nonspace_count = 0
                    continue
            elif char == "]" and not quote:
                level -= 1
                if level == 0:
                    token = "".join(current).strip()
                    current = []
                    nonspace_count = 0
                    if not token:
                        continue
                    if token_index < ignored_prefix_len:
                        assert ignored is not None
                        expected, schema_type = ignored.tokens[token_index]
                        if schema_type is None and token != expected:
                            return None, False, False
                        token_index += 1
                        continue
                    key, has_value = lexer.token_key_and_has_value(token)
                    if has_value:
                        return (
                            "$".join(schema_parts) if schema_parts else None,
                            False,
                            True,
                        )
                    schema_parts.append(key)
                    token_index += 1
                    continue
                if level < 0:
                    return (
                        "$".join(schema_parts) if schema_parts else None,
                        False,
                        True,
                    )

            if level > 0:
                current.append(char)
                if not char.isspace():
                    nonspace_count += 1

        if level > 0 or quote:
            token = "".join(current).strip()
            if token_index < ignored_prefix_len:
                return None, False, False
            ambiguous_sub_schema = not token or not parser._token_has_value(token)
            return (
                "$".join(schema_parts) if schema_parts else None,
                ambiguous_sub_schema,
                True,
            )
        return "$".join(schema_parts) if schema_parts else None, False, True

    def _raise_if_schema_exists(self, method_name: str):
        if len(self.schema) > 0:
            raise ValueError(f"{method_name}() must be called before add_schema()")

    def _raise_if_schema_conflicts(self, schema_name: Optional[str]):
        if schema_name is None:
            raise ValueError("Schema name cannot be None")
        if schema_name in self.schema:
            raise ValueError(f"Schema '{schema_name}' already exists")
        new_parts = schema_name.split("$")
        for existing_name in self.schema:
            existing_parts = existing_name.split("$")
            min_len = min(len(new_parts), len(existing_parts))
            if new_parts[:min_len] == existing_parts[:min_len]:
                raise ValueError(
                    f"Schema '{schema_name}' conflicts with existing schema "
                    f"'{existing_name}'"
                )

    def add_schema(self, schema: str):
        sc = Schema(schema, custom_types=self.custom_types)
        self._raise_if_schema_conflicts(sc.name)
        self.schema[sc.name] = sc
        parts = sc.name.split("$")
        self.schema_roots.add(sc.name.split("$", 1)[0])
        for i in range(1, len(parts)):
            self.schema_prefixes.add("$".join(parts[:i]))
        self._native_backend = None
        return self

    def ignore_prefix(self, prefix: str, save_ignored: bool = False):
        self._raise_if_schema_exists("ignore_prefix")
        self.ignored_prefix = IgnorePrefix(prefix, save_ignored, self.custom_types)
        self._native_backend = None
        return self

    def add_custom_type(self, type_name: str, type_function: Callable[[str], Any]):
        self._raise_if_schema_exists("add_custom_type")
        validate_name(type_name, "custom type")
        if type_name in BUILTIN_TYPES:
            raise ValueError(f"Cannot replace built-in type '{type_name}'")
        if not callable(type_function):
            raise TypeError("custom type converter must be callable")
        self.custom_types[type_name] = type_function
        self._native_backend = None
        return self

    def add_group(self, group_name: str, start_schema: str, end_schema: str):
        if Schema.need_parsing(start_schema):
            start_schema = Schema(start_schema, custom_types=self.custom_types).name
        if Schema.need_parsing(end_schema):
            end_schema = Schema(end_schema, custom_types=self.custom_types).name

        self.groups[group_name] = (
            self.schema[start_schema],
            self.schema[end_schema],
            list(),
        )
        self.group_start[start_schema] = -1
        self.group_end[end_schema] = group_name

    def get_group_index(self, group_name: str) -> List[Tuple[int, int]]:
        result = list()
        for start, end in self.groups[group_name][2]:
            result.append((start, end))
        return result

    def iter_group(self, group_name: str):
        start_schema, end_schema, indices = self.groups[group_name]
        for start, end in indices:
            yield self.data[start : end + 1]

    def post_process(self):
        # 1. Post process groups
        for group in self.groups.values():
            start_schema, end_schema, indices = group
            if (
                start_schema.name in self.group_start
                and self.group_start[start_schema.name] >= 0
            ):
                group[2].append(
                    (self.group_start[start_schema.name], len(self.data) - 1)
                )
        # 2. Post process schema
        for key in self.schema:
            if "$" in key:
                tokens = key.split("$")
                tmp_root = self.result
                final_token = tokens[-1]
                for i in range(len(tokens)):
                    if i == len(tokens) - 1:
                        break
                    if tokens[i] not in tmp_root:
                        tmp_root[tokens[i]] = dict()
                    tmp_root = tmp_root[tokens[i]]
                tmp_root[final_token] = self.schema[key].get_data()
            else:
                self.result[key] = self.schema[key].get_data()

    def _reset_results(self):
        self.data = list()
        self.result = dict()
        for schema in self.schema.values():
            schema.data = list()
        for _, _, indices in self.groups.values():
            indices.clear()
        for schema_name in self.group_start:
            self.group_start[schema_name] = -1

    def append_row_to_data(self, sbsv_data: SbsvData):
        cur_id = self.get_global_id()
        sbsv_data.set_id(cur_id)
        schema = self.schema[sbsv_data.schema_name]
        schema.append_data(sbsv_data)
        self.data.append(sbsv_data)
        if schema.name in self.group_end:
            group_name = self.group_end[schema.name]
            group = self.groups[group_name]
            start_schema = group[0].name
            start_index = self.group_start[start_schema]
            if start_index >= 0:
                if start_schema == schema.name:
                    group[2].append((start_index, cur_id - 1))
                else:
                    group[2].append((start_index, cur_id))
                self.group_start[start_schema] = -1
        if schema.name in self.group_start:
            if self.group_start[schema.name] < 0:
                # Else, it did not meet the end schema
                self.group_start[schema.name] = cur_id

    def _can_use_native(self, content: Optional[str] = None) -> bool:
        if not self.use_native or _native is None:
            return False
        return content is None or "\0" not in content

    def _get_native_backend(self):
        if self._native_backend is None:
            native = _native
            if native is None:
                raise RuntimeError("native parser is unavailable")
            ignored_prefix = None
            save_ignored = False
            ignored = self.ignored_prefix
            if ignored is not None:
                ignored_prefix = ignored.original
                save_ignored = ignored.save_ignored
            self._native_backend = native.compile_parser(
                [schema.original for schema in self.schema.values()],
                self.custom_types,
                SbsvData,
                self.ignore_unknown,
                ignored_prefix,
                save_ignored,
            )
        return self._native_backend

    def _try_load_native(self, content: str) -> bool:
        native = _native
        if native is None or not self._can_use_native(content):
            return False
        try:
            rows = native.parse_rows(self._get_native_backend(), content)
        except native.NativeParseError:
            return False
        for row in rows:
            self.append_row_to_data(row)
        return True

    def _parse_line_python(
        self, line: str, line_number: Optional[int] = None
    ) -> Optional[SbsvData]:
        line = line.strip()
        if len(line) == 0 or line.startswith("#"):
            return None
        schema_name = None
        try:
            if self.ignore_unknown:
                if self._has_unknown_schema_root(line):
                    return None
                if self.ignored_prefix is not None:
                    (
                        schema_name,
                        ambiguous_sub_schema,
                        reliable_schema_name,
                    ) = self._extract_schema_name_fast(line)
                    if reliable_schema_name and not self._schema_name_may_match(
                        schema_name, ambiguous_sub_schema
                    ):
                        return None
            tokens = lexer.tokenize(line, strict=True)
            ignored = dict()
            if self.ignored_prefix is not None:
                tokens, ignored = self.ignored_prefix.parse_tokens(tokens)
            schema_name, tokens = Schema.extract_schema_and_body_tokens(tokens)
            sc = self.match_schema(schema_name, line_number)
            if sc is None:
                return None
            row = sc.parse(tokens)
            if len(ignored) > 0:
                saved_row = ignored.copy()
                saved_row.update(row)
                row = saved_row
            return SbsvData(sc.name, row, -1)
        except ValueError as e:
            raise ValueError(
                parser._build_parse_error_message(e, line_number, schema_name, line)
            ) from e

    def parse_line_detached(
        self, line: str, line_number: Optional[int] = None
    ) -> Optional[SbsvData]:
        native = _native
        if native is not None and self._can_use_native(line):
            try:
                parsed = native.parse_line(
                    self._get_native_backend(), line, line_number or 0
                )
            except native.NativeParseError:
                pass
            else:
                if parsed is None:
                    return None
                return parsed
        return self._parse_line_python(line, line_number)

    def parse_line(self, line: str, line_number: Optional[int] = None):
        sbsv_data = self.parse_line_detached(line, line_number)
        if sbsv_data is None:
            return
        self.append_row_to_data(sbsv_data)

    def load(self, fp: TextIO) -> dict:
        if self._can_use_native() and hasattr(fp, "read"):
            content = fp.read()
            if isinstance(content, str):
                return self.loads(content)
        self._reset_results()
        for line_number, line in enumerate(fp, start=1):
            self.parse_line(line, line_number)
        self.post_process()
        return self.result

    def loads(self, s: str) -> dict:
        self._reset_results()
        if not self._try_load_native(s):
            line_start = 0
            line_number = 1
            while True:
                line_end = s.find("\n", line_start)
                if line_end < 0:
                    row = self._parse_line_python(s[line_start:], line_number)
                    if row is not None:
                        self.append_row_to_data(row)
                    break
                row = self._parse_line_python(s[line_start:line_end], line_number)
                if row is not None:
                    self.append_row_to_data(row)
                line_start = line_end + 1
                line_number += 1
        self.post_process()
        return self.result

    def get_result(self) -> dict:
        return self.result

    def _resolve_schema(self, schema: str) -> Schema:
        if Schema.need_parsing(schema):
            schema = Schema(schema, custom_types=self.custom_types).name
        if schema not in self.schema:
            raise ValueError(f"Invalid schema {schema}")
        return self.schema[schema]

    def get_result_in_order(
        self, schemas: Optional[List[str]] = None
    ) -> List[SbsvData]:
        if schemas is None:
            return self.data
        rows = []
        for schema in schemas:
            data = self._resolve_schema(schema).data
            if data:
                rows.append(data)
        if not rows:
            return []
        if len(rows) == 1:
            return rows[0].copy()
        return list(heapq.merge(*rows, key=attrgetter("id")))

    def get_result_by_index(
        self, schema: str, index: Tuple[int, int]
    ) -> List[SbsvData]:
        data = self._resolve_schema(schema).data
        if index[0] > index[1]:
            return []

        # Lower bound: first row with id >= the inclusive start.
        lo, hi = 0, len(data)
        while lo < hi:
            mid = (lo + hi) // 2
            if data[mid].id < index[0]:
                lo = mid + 1
            else:
                hi = mid
        start = lo

        # Upper bound: first row with id > the inclusive end.
        hi = len(data)
        while lo < hi:
            mid = (lo + hi) // 2
            if data[mid].id <= index[1]:
                lo = mid + 1
            else:
                hi = mid
        return data[start:lo]
