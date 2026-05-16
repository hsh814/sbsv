import unittest
import sbsv


class TestBodyParser(unittest.TestCase):
    def test_body_parser(self):
        parser = sbsv.body_parser("[some: int] [extra: str] [any: str]")

        result = parser.loads("[some 1] [extra str] [any string]")

        self.assertEqual(result, {"some": 1, "extra": "str", "any": "string"})

    def test_body_parser_allows_nullable_first_field(self):
        parser = sbsv.body_parser("[id?: int] [value: int]")

        result = parser.loads("[id] [value 2]")

        self.assertEqual(result, {"id": None, "value": 2})

    def test_body_parser_rejects_invalid_field_name(self):
        with self.assertRaises(ValueError):
            sbsv.body_parser("[bad.name: int]")

    def test_body_parser_as_custom_type(self):
        parser = sbsv.parser()
        body = sbsv.body_parser("[id: int] [value: int]")

        parser.add_custom_type("mytype", body.loads)
        parser.add_schema("[data] [val: mytype]")
        result = parser.loads("[data] [val [id 1] [value 2]]")

        self.assertEqual(result["data"][0]["val"], {"id": 1, "value": 2})


class TestLineParser(unittest.TestCase):
    def test_line_parser(self):
        parser = sbsv.line_parser()
        parser.add_schema("[node] [id: int] [value: int]")
        parser.add_schema("[edge] [src: int] [dst: int] [value: int]")

        result = parser.loads("[node] [id 1] [value 2]")

        self.assertEqual(result.schema_name, "node")
        self.assertEqual(result.data, {"id": 1, "value": 2})
        self.assertEqual(result.id, -1)

    def test_line_parser_sub_schema_and_name_matching(self):
        parser = sbsv.line_parser()
        parser.add_schema("[example] [line] [some: int] [extra: str] [any: str]")

        result = parser.loads(
            "[example] [line] [some 1] [unknown token] [extra str] [any string]"
        )

        self.assertEqual(result.schema_name, "example$line")
        self.assertEqual(result.data, {"some": 1, "extra": "str", "any": "string"})


class TestParserErrors(unittest.TestCase):
    def test_full_line_schema_rejects_nullable_first_field(self):
        parser = sbsv.parser()

        with self.assertRaises(ValueError) as error_context:
            parser.add_schema("[node] [id?: int] [value: int]")

        self.assertIn("first body field", str(error_context.exception))
        self.assertIn("cannot be nullable", str(error_context.exception))

    def test_parse_error_contains_line_schema_input_key_and_type(self):
        parser = sbsv.parser()
        parser.add_schema("[node] [id: int]")

        with self.assertRaises(ValueError) as error_context:
            parser.loads("[node] [id nope]\n")

        message = str(error_context.exception)
        self.assertIn("line=1", message)
        self.assertIn("schema=node", message)
        self.assertIn("input='[node] [id nope]'", message)
        self.assertIn("key 'id'", message)
        self.assertIn("type 'int'", message)


if __name__ == "__main__":
    unittest.main()
