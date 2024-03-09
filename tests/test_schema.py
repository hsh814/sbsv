import unittest
import os
import sbsv

RESOURCE_DIR = os.path.join(os.path.dirname(__file__), "resources")


class TestSchema(unittest.TestCase):
    def test_add_schema(self):
        test_file = os.path.join(RESOURCE_DIR, "test_schema.sbsv")
        parser = sbsv.parser()
        parser.add_schema("[node] [id: int] [value: int]")
        parser.add_schema("[edge] [src: int] [dst: int] [value: int]")
        with open(test_file, "r") as f:
            result = parser.load(f)
        self.assertEqual(len(result["node"]), 4)
        self.assertEqual(len(result["edge"]), 5)

    def test_sub_schema(self):
        test_file = os.path.join(RESOURCE_DIR, "test_schema_sub.sbsv")
        parser = sbsv.parser()
        parser.add_schema("[graph] [node] [id: int] [value: int]")
        parser.add_schema("[graph] [edge] [src: int] [dst: int] [value: int]")
        with open(test_file, "r") as f:
            result = parser.load(f)
        self.assertEqual(len(result["graph$node"]), 4)
        self.assertEqual(len(result["graph$edge"]), 5)
