import unittest
import os
import sbsv

RESOURCE_DIR = os.path.join(os.path.dirname(__file__), "resources")


class TestParser(unittest.TestCase):
    def test_parser_remove(self):
        parser = sbsv.parser()
        parser.add_schema("[mem] [neg] [id: str] [file: str]")
        test_str = "[mem] [neg] id is [id myid] and file is [file myfile!]\n"
        result = parser.loads(test_str)
        self.assertEqual(result["mem"]["neg"][0]["id"], "myid")
        self.assertEqual(result["mem"]["neg"][0]["file"], "myfile!")
