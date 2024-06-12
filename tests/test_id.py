import unittest
import os
import sbsv

RESOURCE_DIR = os.path.join(os.path.dirname(__file__), "resources")


class TestId(unittest.TestCase):
    def test_id(self):
        test_file = os.path.join(RESOURCE_DIR, "test_schema.sbsv")
        parser = sbsv.parser()
        parser.add_schema("[node] [id: int] [value: int]")
        parser.add_schema("[edge] [src: int] [dst: int] [value: int]")
        with open(test_file, "r") as f:
            result = parser.load(f)
        self.assertEqual(len(result["node"]), 4)
        self.assertEqual(len(result["edge"]), 5)
        elems = parser.get_result_in_order(["node", "edge"])
        expected_values = [
            {"id": 1, "value": 2},
            {"id": 2, "value": 3},
            {"src": 1, "dst": 2, "value": 6},
            {"src": 1, "dst": 3, "value": 10},
            {"id": 3, "value": 5},
            {"id": 4, "value": 7},
            {"src": 2, "dst": 3, "value": 15},
            {"src": 4, "dst": 5, "value": 35},
            {"src": 4, "dst": 1, "value": 14},
        ]
        for i, elem in enumerate(elems):
            self.assertEqual(elem.data, expected_values[i])

    def test_id_sub_schema(self):
        test_file = os.path.join(RESOURCE_DIR, "test_schema_sub.sbsv")
        parser = sbsv.parser()
        parser.add_schema("[graph] [node] [id: int] [value: int]")
        parser.add_schema("[graph] [edge] [src: int] [dst: int] [value: int]")
        with open(test_file, "r") as f:
            result = parser.load(f)
        elems = parser.get_result_in_order(["graph$node", "graph$edge"])
        self.assertEqual(len(result["graph"]["node"]), 4)
        self.assertEqual(len(result["graph"]["edge"]), 5)
        self.assertEqual(len(elems), 9)
        self.assertEqual(elems[0].data, {"id": 1, "value": 2})
        self.assertEqual(elems[1].data, {"id": 2, "value": 3})
        self.assertEqual(elems[4].data, {"src": 1, "dst": 2, "value": 6})
