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
        # self.assertEqual(len(result["graph$node"]), 4)
        # self.assertEqual(len(result["graph$edge"]), 5)
        # print(result)
        self.assertEqual(len(result["graph"]["node"]), 4)
        self.assertEqual(len(result["graph"]["edge"]), 5)

    def test_sub_schema_2(self):
        parser = sbsv.parser()
        parser.add_schema(
            "[pacfix] [mem] [neg] [seed: int] [id: int] [hash: int] [time: int] [file: str]"
        )
        parser.add_schema(
            "[pacfix] [mem] [pos] [seed: int] [id: int] [hash: int] [time: int] [file: str]"
        )
        parser.add_schema(
            "[moo] [save] [seed: int] [moo-id: int] [fault: int] [path: bool] [val: int] [file: str] [mut: str] [time: int]"
        )
        parser.add_schema(
            "[vertical] [save] [seed: int] [id: int] [dfg-path: int] [cov: int] [prox: int] [adj: float] [mut: str] [time: int]"
        )
        parser.add_schema("[vertical] [dry-run] [id: int] [dfg-path: int] [res: int]")
        parser.add_schema(
            "[vertical] [valuation] [seed: int] [dfg-path: int] [hash: int] [id: int] [persistent: bool] [time: int]"
        )

    def test_schema_duplicated(self):
        parser = sbsv.parser()
        parser.add_schema(
            "[node] [id$0: int] [value$0: int] [id$1: int] [value$1: int]"
        )
        result = parser.loads("[node] [id 1] [value 2] [id 3] [value 4]\n")
        self.assertEqual(result["node"][0]["id$0"], 1)
        self.assertEqual(result["node"][0]["value$0"], 2)
        self.assertEqual(result["node"][0]["id$1"], 3)
        self.assertEqual(result["node"][0]["value$1"], 4)
