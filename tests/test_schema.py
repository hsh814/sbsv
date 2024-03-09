import unittest
import os
import sbsv

RESOURCE_DIR = os.path.join(os.path.dirname(__file__), "resources")
TEST_FILE = os.path.join(RESOURCE_DIR, "test_schema.sbsv")

class TestSchema(unittest.TestCase):
  def test_add_schema(self):
    parser = sbsv.parser()
    parser.add_schema("[node] [id: int] [value: int]")
    parser.add_schema("[edge] [src: int] [dst: int] [value: int]")
    with open(TEST_FILE, 'r') as f:
      result = parser.load(f)
    