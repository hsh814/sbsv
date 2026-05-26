from typing import List, Dict, Tuple, TextIO, Callable, Any, Optional
import queue
import re
from .utils import unescape_str
import enum

NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


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
    def tokenize(line: str) -> List[str]:
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
                    raise ValueError("Invalid data: unmatched closing bracket")
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
        if quote:
            raise ValueError("Invalid data: unterminated quoted string")
        if level > 0:
            raise ValueError("Invalid data: unterminated bracket")
        if level < 0:
            raise ValueError("Invalid data: unmatched closing bracket")
        return result

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


class SbsvData:
    schema_name: str
    data: Dict[str, Any]
    id: int

    def __init__(self, schema_name: str, data: Dict[str, Any], id: int):
        self.schema_name = schema_name
        self.data = data
        self.id = id

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def __setitem__(self, key: str, value: Any):
        self.data[key] = value

    def __delitem__(self, key: str):
        del self.data[key]

    def __contains__(self, key: str) -> bool:
        return key in self.data

    def __str__(self) -> str:
        return f"[schema {self.schema_name}] [id {self.id}] [data {self.data}]"

    def __repr__(self) -> str:
        return f"SbsvData({self.__str__()})"

    def get_id(self) -> int:
        return self.id

    def get_name(self) -> str:
        return self.schema_name


class SbsvDataType:
    name: str
    name_with_tag: str
    type: str
    nullable: bool
    converter: Callable[[str], Any]
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
        # Complex types
        sub_type = SbsvDataType.list_sub_type(type)
        if sub_type is not None:
            sub_converter = SbsvDataType(sub_type, sub_type, custom_types)
            return lambda x: [sub_converter.convert(v) for v in lexer.tokenize(x)]
        # Custom types
        if type in custom_types:
            return custom_types[type]
        # Unsupported types
        raise ValueError(f"Unsupported type: {type}")

    def convert(self, value: str) -> Any:
        if value == "" and self.nullable:
            return None
        if self.converter is not None:
            if SbsvDataType.list_sub_type(self.type) is None:
                value = unescape_str(value)
            return self.converter(value)
        raise ValueError(f"Unsupported type: {self.type}")

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
        self.original = schema_body
        self.schema = list()
        if custom_types is None:
            custom_types = dict()
        if tokens is None:
            tokens = lexer.tokenize(schema_body)
        if self.original is None:
            self.original = SchemaBody.format_tokens(tokens)
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

        parsed_tokens: List[Tuple[str, str, str]] = []
        for elem in tokens:
            key, value = lexer.token_split_default(elem)
            if key == "":
                raise ValueError(f"Invalid data token [{elem}]: empty name")
            parsed_tokens.append((key, value, elem))

        start = 0
        for schema_type in self.schema:
            done = False
            for i in range(start, len(parsed_tokens)):
                key, value, elem = parsed_tokens[i]
                if not schema_type.check_name(key):
                    continue
                if value == "" and not schema_type.check_nullable():
                    raise ValueError(
                        f"Invalid data token [{elem}]: empty value for "
                        f"non-nullable key '{schema_type.name}'"
                    )
                try:
                    result[schema_type.key()] = schema_type.convert(value)
                except Exception as e:
                    raise ValueError(
                        f"Invalid value for key '{schema_type.name}' "
                        f"as type '{schema_type.type}': {value!r}"
                    ) from e
                start = i + 1
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
        tokens = lexer.tokenize(s)
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
        tokens = lexer.tokenize(line)
        return Schema.extract_schema_and_body_tokens(tokens)

    @staticmethod
    def extract_schema_and_body_tokens(
        tokens: List[str],
    ) -> Tuple[Optional[str], List[str]]:
        name: Optional[str] = None
        data: List[str] = list()
        may_have_sub_schema = True
        for i in range(len(tokens)):
            key, value = lexer.token_split_default(tokens[i])
            if key != "" and value == "" and may_have_sub_schema:
                if name is None:
                    name = key
                else:
                    name = f"{name}${key}"
            else:
                may_have_sub_schema = False
                data.append(tokens[i])
        return name, data

    def parse(self, tokens: List[str]) -> Dict[str, Any]:
        return self.body.parse(tokens)

    def get_data(self) -> List[SbsvData]:
        return self.data

    def append_data(self, data: SbsvData):
        self.data.append(data)


class IgnorePrefix:
    tokens: List[Tuple[str, Optional[SbsvDataType]]]
    save_ignored: bool

    def __init__(
        self,
        prefix: str,
        save_ignored: bool = False,
        custom_types: Optional[Dict[str, Callable[[str], Any]]] = None,
    ):
        tokens = lexer.tokenize(prefix)
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
        return self.parse_tokens(lexer.tokenize(s))

    def parse_tokens(self, tokens: List[str]) -> Dict[str, Any]:
        return self.body.parse(tokens)

    def add_custom_type(self, type_name: str, type_function: Callable[[str], Any]):
        self.custom_types[type_name] = type_function
        return self


class parser:
    schema: Dict[str, Schema]
    ignore_unknown: bool
    ignored_prefix: Optional[IgnorePrefix]
    custom_types: Dict[str, Callable[[str], Any]]
    data: List[SbsvData]
    groups: Dict[str, Tuple[Schema, Schema, List[Tuple[int, int]]]]
    group_start: Dict[str, int]
    group_end: Dict[str, str]
    result: dict

    def __init__(self, ignore_unknown: bool = True):
        self.schema = dict()
        self.ignore_unknown = ignore_unknown
        self.ignored_prefix = None
        self.custom_types = dict()
        self.data = list()
        self.result = dict()
        self.groups = dict()
        self.group_start = dict()
        self.group_end = dict()

    # New parser with same schema
    def clone(self) -> "parser":
        result = parser(self.ignore_unknown)
        result.schema = self.schema.copy()
        result.groups = self.groups.copy()
        result.ignored_prefix = self.ignored_prefix
        result.custom_types = self.custom_types.copy()
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
        return len(token.strip().split(None, maxsplit=1)) > 1

    def _schema_name_may_match(
        self, schema_name: Optional[str], ambiguous_sub_schema: bool
    ) -> bool:
        if schema_name is None:
            return False
        if schema_name in self.schema:
            return True
        if not ambiguous_sub_schema:
            return False
        prefix = f"{schema_name}$"
        return any(existing_name.startswith(prefix) for existing_name in self.schema)

    def _scan_schema_name_prefix(self, line: str) -> Tuple[Optional[str], bool]:
        ignored_prefix_len = 0
        if self.ignored_prefix is not None:
            ignored_prefix_len = len(self.ignored_prefix.tokens)

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
                        token_index += 1
                        continue
                    if parser._token_has_value(token):
                        return "$".join(schema_parts) if schema_parts else None, False
                    schema_parts.append(token)
                    token_index += 1
                    continue
                if level < 0:
                    return "$".join(schema_parts) if schema_parts else None, False

            if level > 0:
                current.append(char)
                if not char.isspace():
                    nonspace_count += 1

        if level > 0 or quote:
            token = "".join(current).strip()
            ambiguous_sub_schema = not token or not parser._token_has_value(token)
            return (
                "$".join(schema_parts) if schema_parts else None,
                ambiguous_sub_schema,
            )
        return "$".join(schema_parts) if schema_parts else None, False

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
        return self

    def ignore_prefix(self, prefix: str, save_ignored: bool = False):
        self._raise_if_schema_exists("ignore_prefix")
        self.ignored_prefix = IgnorePrefix(prefix, save_ignored, self.custom_types)
        return self

    def add_custom_type(self, type_name: str, type_function: Callable[[str], Any]):
        self._raise_if_schema_exists("add_custom_type")
        self.custom_types[type_name] = type_function
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

    def append_row_to_data(self, schema: Schema, row: Dict[str, Any]):
        cur_id = self.get_global_id()
        sbsv_data = SbsvData(schema.name, row, cur_id)
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

    def parse_line_detached(
        self, line: str, line_number: Optional[int] = None
    ) -> Optional[SbsvData]:
        line = line.strip()
        if len(line) == 0 or line.startswith("#"):
            return None
        schema_name = None
        try:
            try:
                tokens = lexer.tokenize(line)
            except ValueError:
                if self.ignore_unknown:
                    schema_name, ambiguous_sub_schema = self._scan_schema_name_prefix(
                        line
                    )
                    if not self._schema_name_may_match(
                        schema_name, ambiguous_sub_schema
                    ):
                        return None
                raise
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

    def parse_line(self, line: str, line_number: Optional[int] = None):
        sbsv_data = self.parse_line_detached(line, line_number)
        if sbsv_data is None:
            return
        self.append_row_to_data(self.schema[sbsv_data.schema_name], sbsv_data.data)

    def load(self, fp: TextIO) -> dict:
        for line_number, line in enumerate(fp, start=1):
            self.parse_line(line, line_number)
        self.post_process()
        return self.result

    def loads(self, s: str) -> dict:
        for line_number, line in enumerate(s.split("\n"), start=1):
            self.parse_line(line, line_number)
        self.post_process()
        return self.result

    def get_result(self) -> dict:
        return self.result

    def get_result_in_order(
        self, schemas: Optional[List[str]] = None
    ) -> List[SbsvData]:
        if schemas is None:
            return self.data
        pq = queue.PriorityQueue()
        for schema in schemas:
            if Schema.need_parsing(schema):
                schema = Schema(schema, custom_types=self.custom_types).name
            if schema not in self.schema:
                raise ValueError(f"Invalid schema {schema}")
            cur_schema = self.schema[schema]
            if len(cur_schema.get_data()) == 0:
                continue
            pq.put((cur_schema.get_data()[0].get_id(), cur_schema, 0))
        result = list()
        while not pq.empty():
            value, cur_schema, elem = pq.get()
            result.append(cur_schema.get_data()[elem])
            if elem < len(cur_schema.get_data()) - 1:
                next_value = cur_schema.get_data()[elem + 1].get_id()
                pq.put((next_value, cur_schema, elem + 1))
        return result

    def get_result_by_index(
        self, schema: str, index: Tuple[int, int]
    ) -> List[SbsvData]:
        if Schema.need_parsing(schema):
            schema = Schema(schema, custom_types=self.custom_types).name
        if schema not in self.schema:
            raise ValueError(f"Invalid schema {schema}")

        data = self.schema[schema].get_data()

        # Binary search for the start index
        start = 0
        end = len(data) - 1
        start_index = -1

        while start <= end:
            if end - start < 8:
                # Just use linear search
                for i in range(start, end + 1):
                    if data[i].get_id() >= index[0]:
                        start_index = i
                        break
            mid = (start + end) // 2
            if data[mid].get_id() >= index[0]:
                start_index = mid
                end = mid - 1
            else:
                start = mid + 1

        if start_index == -1:
            return []

        # Binary search for the end index
        start = start_index
        end = len(data) - 1
        end_index = -1

        while start <= end:
            if end - start < 8:
                # Just use linear search
                for i in range(start, end + 1):
                    if data[i].get_id() <= index[1]:
                        end_index = i
                        break
            mid = (start + end) // 2
            if data[mid].get_id() <= index[1]:
                end_index = mid
                start = mid + 1
            else:
                end = mid - 1
        return data[start_index : end_index + 1]
