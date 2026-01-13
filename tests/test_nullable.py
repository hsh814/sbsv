import unittest
import os
import sbsv

RESOURCE_DIR = os.path.join(os.path.dirname(__file__), "resources")


class TestNullable(unittest.TestCase):
    def test_nullable(self):
        parser = sbsv.parser()
        parser.add_schema("[mem] [neg] [id: str] [file?: str]")
        test_str = "[mem] [neg] id is [id myid] and file is [file]\n"
        test_str += "[mem] [neg] id is [id myid2] and file is [file [myfile2!]]\n"
        result = parser.loads(test_str)
        self.assertEqual(result["mem"]["neg"][0]["id"], "myid")
        self.assertEqual(result["mem"]["neg"][0]["file"], None)
        self.assertEqual(result["mem"]["neg"][1]["id"], "myid2")
        self.assertEqual(result["mem"]["neg"][1]["file"], "[myfile2!]")
    
    # def test_nullable_first(self):
    #     parser = sbsv.parser()
    #     parser.add_schema("[mem] [neg] [id?: str] [file: str]")
    #     test_str = "[mem] [neg] id is [id myid] and file is [file file1]\n"
    #     test_str += "[mem] [neg] id is [id] and file is [file [myfile2!]]\n"
    #     result = parser.loads(test_str)
    #     self.assertEqual(result["mem"]["neg"][0]["id"], "myid")
    #     self.assertEqual(result["mem"]["neg"][0]["file"], "file1")
    #     self.assertEqual(result["mem"]["neg"][1]["id"], None)
    #     self.assertEqual(result["mem"]["neg"][1]["file"], "[myfile2!]")
