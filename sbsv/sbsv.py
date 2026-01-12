from typing import List, Dict, Tuple, Set, TextIO, Callable, Any
import queue
from .utils import get_schema_id, get_schema_name_list, escape_str, unescape_str
import enum


# Global registry for custom types: name -> converter(str) -> Any
CUSTOM_TYPES: Dict[str, Callable[[str], Any]] = dict()


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
    def update_token(result: List[str], current: str, should_replace: bool):
        current = current.strip()
        if should_replace:
            current = unescape_str(current)
        result.append(current)

    @staticmethod
    def tokenize(line: str) -> List[str]:
        result = list()
        level = 0
        current = ""
        escape = False
        should_replace = False
        for c in range(len(line)):
            char = line[c]
            if escape:
                escape = False
                current += "\\" + char
                continue
            if char == "\\":
                escape = True
                should_replace = True
                continue
            if char == "[":
                level += 1
                if level == 1:
                    if len(current.strip()) > 0:
                        lexer.update_token(result, current, should_replace)
                        should_replace = False
                    current = ""
                    continue
            elif char == "]":
                level -= 1
                if level == 0:
                    lexer.update_token(result, current, should_replace)
                    should_replace = False
                    current = ""
                    continue
            if level > 0:
                current += char
        return result

    @staticmethod
    def token_split(token: str, delimiter: str) -> Tuple[str, str]:
        tokens = token.split(delimiter, maxsplit=1)
        if len(tokens) == 0:
            return "", ""
        if len(tokens) == 1:
            return tokens[0].strip(), ""
        return tokens[0].strip(), tokens[1].strip()

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

    def __init__(self, name_with_tag: str, type: str):
        self.nullable = name_with_tag.endswith("?")
        if self.nullable:
            name_with_tag = name_with_tag[:-1]
        self.name_with_tag = name_with_tag
        if "$" in self.name_with_tag:
            tokens = self.name_with_tag.split("$")
            self.name = tokens[0]
        else:
            self.name = name_with_tag
        self.type = type
        self.converter = self.add_converter(type)
        self.sub_type = list()

    @staticmethod
    def to_bool(value: str) -> bool:
        value = value.strip().lower()
        if value in ["t", "true", "y", "yes", "1"]:
            return True
        elif value in ["f", "false", "n", "no", "0"]:
            return False
        raise ValueError(f"Invalid boolean value: {value}")

    def add_converter(self, type: str) -> Callable[[str], Any]:
        # Primitive types
        if type == "int":
            return int
        if type == "float":
            return float
        if type == "str":
            return str
        if type == "bool":
            return SbsvDataType.to_bool
        # Complex types
        if type.startswith("list"):
            sub_type = type[5:-1]
            return lambda x: [
                SbsvDataType(sub_type, sub_type).convert(v) for v in lexer.tokenize(x)
            ]
        # Custom types
        if type in CUSTOM_TYPES:
            return CUSTOM_TYPES[type]
        # Unsupported types
        return None

    def convert(self, value: str) -> Any:
        if value == "" and self.nullable:
            return None
        if self.converter is not None:
            return self.converter(value)
        # Late-bound custom type
        if self.type in CUSTOM_TYPES:
            self.converter = CUSTOM_TYPES[self.type]
            return self.converter(value)
        return value

    def key(self) -> str:
        return self.name_with_tag

    def check_nullable(self) -> bool:
        return self.nullable

    def check_name(self, name: str) -> bool:
        return self.name == name


class Schema:
    original: str
    name: str
    schema: List[SbsvDataType]
    data: List[SbsvData]

    def __init__(self, s: str):
        self.original = s
        self.name = ""
        self.schema = list()
        self.data = list()
        tokens = lexer.tokenize(s)
        if len(tokens) == 0:
            raise ValueError(f"Invalid schema {s}: too short")
        self.name = tokens[0]
        for i in range(1, len(tokens)):
            key, value = lexer.token_split_default(tokens[i])
            if key == "":
                raise ValueError(f"Invalid schema {tokens[i]}: empty name")
            # Sub schema
            if value == "":
                self.name = f"{self.name}${key}"
                continue
            key, value = lexer.token_split_schema(tokens[i])
            # Normal schema
            self.schema.append(SbsvDataType(key, value))

    @staticmethod
    def need_parsing(s: str) -> bool:
        return s.startswith("[") and s.endswith("]")

    @staticmethod
    def preprocess(line: str) -> Tuple[str, List[str]]:
        tokens = lexer.tokenize(line)
        name: str = None
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
        result = dict()
        if len(tokens) < len(self.schema):
            raise ValueError(f"Invalid data {tokens}: too short")
        q = queue.Queue(len(tokens))
        for token in tokens:
            q.put(token)
        for schema_type in self.schema:
            done = False
            while not q.empty():
                elem = q.get()
                key, value = lexer.token_split_default(elem)
                if key == "":
                    raise ValueError(f"Invalid data {elem}: empty name")
                if not schema_type.check_name(key):
                    continue
                if value == "" and not schema_type.check_nullable():
                    raise ValueError(f"Invalid data {elem}: empty value")
                result[schema_type.key()] = schema_type.convert(value)
                done = True
                break
            if not done:
                raise ValueError(f"Invalid data {tokens}: missing key")
        return result

    def get_data(self) -> List[SbsvData]:
        return self.data

    def append_data(self, data: SbsvData):
        self.data.append(data)


class parser:
    data: List[SbsvData]
    groups: Dict[str, Tuple[Schema, Schema, List[Tuple[int, int]]]]
    group_start: Dict[str, int]
    group_end: Dict[str, str]
    result: dict
    schema: Dict[str, Schema]
    ignore_unknown: bool

    def __init__(self, ignore_unknown: bool = True):
        self.data = list()
        self.result = dict()
        self.schema = dict()
        self.groups = dict()
        self.group_start = dict()
        self.group_end = dict()
        self.ignore_unknown = ignore_unknown

    # New parser with same schema
    def clone(self) -> "parser":
        result = parser(self.ignore_unknown)
        result.schema = self.schema.copy()
        result.groups = self.groups.copy()
        return result

    def get_global_id(self) -> int:
        return len(self.data)

    def match_schema(self, line: str) -> Tuple[Schema, List[str]]:
        name, value = Schema.preprocess(line)
        if name not in self.schema:
            if self.ignore_unknown:
                return None, None
            raise ValueError(f"Invalid schema {name} at: {line}")
        return self.schema[name], value

    def add_schema(self, schema: str):
        # 1. tokenize
        sc = Schema(schema)
        self.schema[sc.name] = sc

    def add_custom_type(self, type_name: str, type_function: Callable[[str], Any]):
        CUSTOM_TYPES[type_name] = type_function
        return self

    def add_group(self, group_name: str, start_schema: str, end_schema: str):
        if Schema.need_parsing(start_schema):
            start_schema = Schema(start_schema).name
        if Schema.need_parsing(end_schema):
            end_schema = Schema(end_schema).name

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

    def parse_line(self, line: str):
        line = line.strip()
        if len(line) == 0 or line.startswith("#"):
            return
        sc, tokens = self.match_schema(line)
        if sc is None:
            return
        row = sc.parse(tokens)
        self.append_row_to_data(sc, row)

    def load(self, fp: TextIO) -> dict:
        for line in fp:
            self.parse_line(line)
        self.post_process()
        return self.result

    def loads(self, s: str) -> dict:
        for line in s.split("\n"):
            self.parse_line(line)
        self.post_process()
        return self.result

    def get_result(self) -> dict:
        return self.result

    def get_result_in_order(self, schemas: List[str] = None) -> List[SbsvData]:
        if schemas is None:
            return self.data
        pq = queue.PriorityQueue()
        for schema in schemas:
            if Schema.need_parsing(schema):
                schema = Schema(schema).name
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
            schema = Schema(schema).name
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
