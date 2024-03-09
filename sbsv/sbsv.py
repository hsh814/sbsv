from typing import List, Dict, Tuple, Set, TextIO, Callable, Any


class lexer:
  def __init__(self):
    pass
  @staticmethod
  def tokenize(line: str) -> List[str]:
    result = list()
    level = 0
    current = ""
    for c in range(len(line)):
      char = line[c]
      if char == '[':
        level += 1
        if level == 1:
          if len(current.strip()) > 0:
            result.append(current.strip())
          current = ""
          continue
      elif char == ']':
        level -= 1
        if level == 0:
          result.append(current.strip())
          current = ""
          continue
      if level > 0:
        current += char
    if len(current.strip()) > 0:
      result.append(current.strip())
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
    return lexer.token_split(token, ':')

class SbsvDataType:
  name: str
  type: str
  converter: Callable[[str], Any]
  sub_type: List["SbsvDataType"]
  def __init__(self, name: str, type: str):
    self.name = name
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
      return lambda x: [SbsvDataType(sub_type, sub_type).convert(v) for v in lexer.tokenize(x)]
    # Unsupported types
    return None
  def convert(self, value: str) -> Any:
    if self.converter is not None:
      return self.converter(value)
    return value

class SbsvData:
  name: str
  type: str
  def __init__(self, name: str, type: str):
    self.name = name
    self.type = type

class Schema:
  original: str
  name: str
  schema: List[SbsvDataType]
  def __init__(self, s: str):
    self.original = s
    self.name = ""
    self.schema = list()
    tokens = lexer.tokenize(s)
    if len(tokens) <= 1:
      raise ValueError("Invalid schema: too short")
    self.name = tokens[0]
    may_have_sub_schema = True
    for i in range(1, len(tokens)):
      key, value = lexer.token_split_default(tokens[i])
      if key == "":
        raise ValueError("Invalid schema: empty name")
      # Sub schema
      if value == "":
        if may_have_sub_schema:
          self.name = f"{self.name}${key}"
          may_have_sub_schema = False
        else:
          raise ValueError("Invalid schema: empty value")
        continue
      # Normal schema
      self.schema.append(SbsvDataType(key, value))
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
      raise ValueError("Invalid data: too short")
    for i in range(len(self.schema)):
      schema_type = self.schema[i]
      key, value = lexer.token_split_default(tokens[i])
      if key == "":
        raise ValueError("Invalid data: empty name")
      if value == "":
        raise ValueError("Invalid data: empty value")
      result[key] = schema_type.convert(value)
    return result

class parser:
  data: dict
  schema: Dict[str, Schema]
  ignore_unknown: bool
  def __init__(self, ignore_unknown: bool = True):
    self.data = dict()
    self.schema = dict()
    self.ignore_unknown = ignore_unknown
  # New parser with same schema
  def clone(self) -> "parser":
    result = parser(self.ignore_unknown)
    result.schema = self.schema.copy()
    return result
  def match_schema(self, line: str) -> Tuple[Schema, List[str]]:
    name, value = Schema.preprocess(line)
    if name not in self.schema:
      if self.ignore_unknown:
        return None, None
      raise ValueError(f"Schema not found: {name}")
    return self.schema[name], value
  def add_schema(self, schema: str):
    # 1. tokenize
    sc = Schema(schema)
    self.schema[sc.name] = sc
    self.data[sc.name] = list()
  def append_row_to_data(self, schema: Schema, row: Dict[str, Any]):
    self.data[schema.name].append(row)
  def parse_line(self, line: str):
    sc, tokens = self.match_schema(line)
    if sc is None:
      return
    row = sc.parse(tokens)
    self.append_row_to_data(sc, row)
  def load(self, fp: TextIO) -> dict:
    return self.loads(fp.read())
  def loads(self, s: str) -> dict:
    for line in s.split('\n'):
      line = line.strip()
      if len(line) == 0 or line.startswith('#'):
        continue
      self.parse_line(line)
    return self.data

