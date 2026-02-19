import unittest
import os
import sbsv

RESOURCE_DIR = os.path.join(os.path.dirname(__file__), "resources")


class TestParser(unittest.TestCase):
    def test_parser_remove(self):
        parser = sbsv.parser()
        parser.add_schema("[mem] [neg] [id: str] [file: str]")
        test_str = "[mem] [neg] id is [id myid] and file is [file myfile!]\n"
        test_str += "[mem] [neg] id is [id myid2] and file is [file [myfile2!]]\n"
        result = parser.loads(test_str)
        self.assertEqual(result["mem"]["neg"][0]["id"], "myid")
        self.assertEqual(result["mem"]["neg"][0]["file"], "myfile!")
        self.assertEqual(result["mem"]["neg"][1]["id"], "myid2")
        self.assertEqual(result["mem"]["neg"][1]["file"], "[myfile2!]")

    def test_parser_name_matching(self):
        parser = sbsv.parser()
        parser.add_schema("[mem] [neg] [id: str] [file: str]")
        parser.add_schema(
            "[mem] [both] [id$neg: str] [file$neg: str] [id$pos: str] [file$pos: str]"
        )
        test_str = "[mem] [neg] [id myid] [this is unknown] [file myfile!]\n"
        test_str += "[mem] [both] [id myid] [file myfile!] [id myid2] [file myfile2!] [at the end]\n"
        test_str += "[mem] [both] [id myid] [fake id] [file myfile!] [my-id hehe] [id myid3] [file myfile3!]\n"
        result = parser.loads(test_str)
        self.assertEqual(result["mem"]["neg"][0]["id"], "myid")
        self.assertEqual(result["mem"]["neg"][0]["file"], "myfile!")
        self.assertEqual(result["mem"]["both"][0]["id$neg"], "myid")
        self.assertEqual(result["mem"]["both"][0]["file$neg"], "myfile!")
        self.assertEqual(result["mem"]["both"][0]["id$pos"], "myid2")
        self.assertEqual(result["mem"]["both"][0]["file$pos"], "myfile2!")
        self.assertEqual(result["mem"]["both"][1]["id$neg"], "myid")
        self.assertEqual(result["mem"]["both"][1]["file$neg"], "myfile!")
        self.assertEqual(result["mem"]["both"][1]["id$pos"], "myid3")
        self.assertEqual(result["mem"]["both"][1]["file$pos"], "myfile3!")

    def test_error_message_with_unknown_schema_context(self):
        parser = sbsv.parser(ignore_unknown=False)
        parser.add_schema("[node] [id: int]")

        with self.assertRaises(ValueError) as error_context:
            parser.loads("[edge] [id 1]\n")

        message = str(error_context.exception)
        self.assertIn("line=1", message)
        self.assertIn("schema=edge", message)

    def test_error_message_with_parse_schema_context(self):
        parser = sbsv.parser()
        parser.add_schema("[node] [id: int] [value: int]")

        with self.assertRaises(ValueError) as error_context:
            parser.loads("[node] [id 1]\n")

        message = str(error_context.exception)
        self.assertIn("line=1", message)
        self.assertIn("schema=node", message)
