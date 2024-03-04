from typing import List, Dict, Tuple, Set, TextIO


class parser:
  data: dict
  schema: dict
  def __init__(self, data: List[List[tuple]]):
    self.data = dict()
    self.schema = dict()
  def add_schema(self, schema: str):
    # 1. tokenize
    tokens = self.parser_level_1(schema)
    # 2. parse
    for token in tokens:
      key, value = self.parser_default(token)
    self.schema[tokens[0]] = value
  def load(self, fp: TextIO):
    return self.loads(fp.read())
  def loads(self, s: str):
    for line in s.split('\n'):
      line = line.strip()
  def parser_default(self, token: str) -> Tuple[str, str]:
    tokens = token.split(maxsplit=1)
    if len(tokens) == 1:
      return tokens[0], ""
    return tokens[0], tokens[1]
  def parser_level_1(self, line: str) -> List[str]:
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