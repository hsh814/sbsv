import unittest
import os
import sbsv

RESOURCE_DIR = os.path.join(os.path.dirname(__file__), "resources")


class TestGroup(unittest.TestCase):
    def test_group(self):
        parser = sbsv.parser()
        parser.add_schema("[data] [begin]")
        parser.add_schema("[data] [end]")
        parser.add_schema("[block] [data: int]")
        parser.add_group("data", "[data] [begin]", "[data] [end]")
        test_file = os.path.join(RESOURCE_DIR, "test_group.sbsv")
        with open(test_file, "r") as f:
            parser.load(f)

        expected_groups = [[1, 2], [3, 4]]
        expected_indices = [(0, 3), (4, 7)]

        for i, block in enumerate(parser.iter_group("data")):
            group = list()
            for block_data in block:
                if block_data.schema_name == "block":
                    group.append(block_data["data"])
            self.assertEqual(group, expected_groups[i])

        block_indices = parser.get_group_index("data")
        self.assertEqual(block_indices, expected_indices)

        for i, index in enumerate(block_indices):
            group = list()
            for block in parser.get_result_by_index("[block]", index):
                group.append(block["data"])
            self.assertEqual(group, expected_groups[i])

    def test_group_wo_closing(self):
        parser = sbsv.parser()
        parser.add_schema("[group-wo-closing] [new-group: str]")
        parser.add_schema("[some] [data: int]")
        parser.add_group("new-group", "[group-wo-closing]", "[group-wo-closing]")
        test_file = os.path.join(RESOURCE_DIR, "test_group_wo_closing.sbsv")
        with open(test_file, "r") as f:
            parser.load(f)

        expected_groups = [[9, 8, 7], [6, 5], [4]]
        expected_indices = [(0, 3), (4, 6), (7, 8)]
        count = 0

        for i, block in enumerate(parser.iter_group("new-group")):
            group = list()
            for block_data in block:
                if block_data.schema_name == "some":
                    group.append(block_data["data"])
            self.assertEqual(group, expected_groups[i])
            count += 1
        self.assertEqual(count, len(expected_groups))

        block_indices = parser.get_group_index("new-group")
        self.assertEqual(block_indices, expected_indices)
        count = 0
        for i, index in enumerate(block_indices):
            group = list()
            for block in parser.get_result_by_index("some", index):
                group.append(block["data"])
            self.assertEqual(group, expected_groups[i])
            count += 1
        self.assertEqual(count, len(expected_groups))
