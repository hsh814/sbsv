import unittest
import os
import sbsv
from sbsv.sbsv import lexer

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
        self.assertEqual(sbsv.escape_str(",|]][[]]"), ",|\\]\\][[]]")
        self.assertEqual(sbsv.escape_str("[matched]"), "[matched]")
        self.assertEqual(sbsv.escape_str("[matched]", quote=True), '"[matched]"')
        self.assertEqual(
            sbsv.escape_str('[quoted "value"]', quote=True), '"[quoted \\"value\\"]"'
        )
        self.assertEqual(sbsv.unescape_str("this is a test"), "this is a test")
        self.assertEqual(sbsv.unescape_str("this is a test\\]"), "this is a test]")
        self.assertEqual(sbsv.unescape_str("this is a test\\\\"), "this is a test\\")
        self.assertEqual(sbsv.unescape_str(",|\\]\\][[]]"), ",|]][[]]")
        self.assertEqual(
            sbsv.escape_str("comma, colon: slash/"), "comma, colon: slash/"
        )
        self.assertEqual(
            sbsv.unescape_str('"[quoted \\"value\\"]"'), '[quoted "value"]'
        )
        self.assertEqual(
            sbsv.unescape_str(sbsv.escape_str("should escape ]]\\ this")),
            "should escape ]]\\ this",
        )
        self.assertEqual(sbsv.unescape_str('" a "'), " a ")
        self.assertEqual(sbsv.unescape_str('  "a"  '), "a")
        with self.assertRaises(ValueError):
            sbsv.unescape_str('"a\\q"')
        with self.assertRaises(ValueError):
            sbsv.unescape_str('"unterminated')

    def test_escape_roundtrip_all_mapped_chars(self):
        values = [
            "a\bb",
            "a\tb",
            "a\nb",
            "a\fb",
            "a\rb",
            'a"b',
            "a\\b",
            "a[b",
            "a]b",
            "a[b]c",
        ]
        for value in values:
            with self.subTest(value=value):
                self.assertEqual(sbsv.unescape_str(sbsv.escape_str(value)), value)

    def test_quoted_string_keeps_internal_brackets(self):
        parser = sbsv.parser()
        parser.add_schema("[data] [value: str]")

        result = parser.loads('[data] [value "[internal] \\"quote\\""]\n')

        self.assertEqual(result["data"][0]["value"], '[internal] "quote"')

    def test_unquoted_balanced_brackets_do_not_need_escape(self):
        parser = sbsv.parser()
        parser.add_schema("[data] [value: str]")

        result = parser.loads("[data] [value [internal] value]\n")

        self.assertEqual(result["data"][0]["value"], "[internal] value")

    def test_unquoted_quote_inside_value_is_literal(self):
        parser = sbsv.parser()
        parser.add_schema("[data] [value: str]")

        result = parser.loads('[data] [value internal "quote]\n')

        self.assertEqual(result["data"][0]["value"], 'internal "quote')

    def test_escape_str_output_parses_back_to_original_value(self):
        values = [
            "a\ttab",
            "a\nnewline",
            'a"quote',
            "a\\backslash",
            "a]close",
            "a[open",
        ]
        for value in values:
            with self.subTest(value=value):
                parser = sbsv.parser()
                parser.add_schema("[data] [value: str]")
                result = parser.loads(f"[data] [value {sbsv.escape_str(value)}]\n")
                self.assertEqual(result["data"][0]["value"], value)

    def test_tokenize_default_is_best_effort_for_malformed_input(self):
        self.assertEqual(lexer.tokenize("[known] [id 1"), ["known"])
        self.assertEqual(lexer.tokenize('[known] [value "broken'), ["known"])

        with self.assertRaises(ValueError):
            lexer.tokenize("[known] [id 1", strict=True)
