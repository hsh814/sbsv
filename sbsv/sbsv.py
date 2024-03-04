from typing import List, Dict, Set, Tuple, Optional, TextIO

class parser():
  _data: dict = dict()
  def __init__(self):
    pass
  def load(self, file: TextIO) -> dict:
    return self.loads(file.read())
  def loads(self, text: str) -> dict:
    self._data = dict()
    for line in text.split('\n'):
      line = line.strip()
      if line.startswith('#') or len(line) == 0:
        continue
      key, value = line.split('[')
      key = key.strip()
      value = value.strip()[:-1]
      self._data[key] = value.split('][')
    return self._data