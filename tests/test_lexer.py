import unittest
import os
import sbsv

RESOURCE_DIR = os.path.join(os.path.dirname(__file__), "resources")


class TestLexer(unittest.TestCase):
    def test_lexer(self):
        parser = sbsv.parser()
        parser.add_schema("[mem] [neg] [id: str] [file: str]")
        parser.add_schema("[mem] [pos] [seed: int] [id: str] [file: str]")
        test_str = "[mem] [neg] [id str can have spaces] [file /path/to/file]\n"
        result = parser.loads(test_str)
        self.assertEqual(result["mem"]["neg"][0]["id"], "str can have spaces")

    def test_lexer_escape(self):
        parser = sbsv.parser()
        parser.add_schema("[mem] [neg] [id: str] [file: str]")
        parser.add_schema("[mem] [pos] [seed: int] [id: str] [file: str]")
        test_str = "[mem] [neg] [id should escape \\] this] [file /path/to/file]\n"
        test_str += '[mem] [pos] [seed 123] [id should escape \\]\\]\\ this] [file /path/to/file\\"]\n'
        result = parser.loads(test_str)
        self.assertEqual(result["mem"]["neg"][0]["id"], "should escape ] this")
        self.assertEqual(result["mem"]["pos"][0]["id"], "should escape ]]\\ this")
        self.assertEqual(result["mem"]["pos"][0]["file"], '/path/to/file"')

    def test_lexer_escape_file(self):
        parser = sbsv.parser()
        parser.add_schema("[mem] [neg] [id: str] [file: str]")
        parser.add_schema("[mem] [pos] [seed: int] [id: str] [file: str]")
        with open(os.path.join(RESOURCE_DIR, "test_lexer_escape.sbsv"), "r") as f:
            result = parser.load(f)
        self.assertEqual(result["mem"]["neg"][0]["id"], "should escape ] this")
        self.assertEqual(result["mem"]["pos"][0]["id"], "should escape ]]\\ this")
        self.assertEqual(result["mem"]["pos"][0]["file"], '/path/to/file"')

    def test_lexer_remove(self):
        parser = sbsv.parser()
        parser.add_schema("[mem] [neg] [id: str] [file: str]")
        test_str = "[mem] [neg] id is [id myid] and file is [file myfile!]\n"
        result = parser.loads(test_str)
        self.assertEqual(result["mem"]["neg"][0]["id"], "myid")
        self.assertEqual(result["mem"]["neg"][0]["file"], "myfile!")

    def test_escpae(self):
        self.assertEqual(sbsv.escape_str("this is a test"), "this is a test")
        self.assertEqual(sbsv.escape_str("this is a test]"), "this is a test\\]")
        self.assertEqual(sbsv.escape_str("this is a test\\"), "this is a test\\\\")
        self.assertEqual(sbsv.escape_str(",|]][[]]"), "\\,|\\]\\]\\[\\[\\]\\]")
        self.assertEqual(sbsv.unescape_str("this is a test"), "this is a test")
        self.assertEqual(sbsv.unescape_str("this is a test\\]"), "this is a test]")
        self.assertEqual(sbsv.unescape_str("this is a test\\\\"), "this is a test\\")
        self.assertEqual(sbsv.unescape_str("\\,|\\]\\]\\[\\[\\]"), ",|]][[]")
        self.assertEqual(
            sbsv.unescape_str(sbsv.escape_str("should escape ]]\\ this")),
            "should escape ]]\\ this",
        )
