import unittest

import sbsv


class TestNativeBackend(unittest.TestCase):
    @unittest.skipUnless(sbsv.native_available(), "native extension is unavailable")
    def test_native_and_python_backends_match(self):
        schema = (
            "[event] [metric] [id: int] [value: float] [active: bool] "
            "[tags: list[str]] [message: str]"
        )
        content = (
            "[event] [metric] [id 9223372036854775808] [value 42.5] "
            "[active true] [tags [one] [two]] [message some payload]\n"
        )

        native_parser = sbsv.parser()
        native_parser.add_schema(schema)
        python_parser = sbsv.parser(use_native=False)
        python_parser.add_schema(schema)

        native_row = native_parser.loads(content)["event"]["metric"][0]
        python_row = python_parser.loads(content)["event"]["metric"][0]

        self.assertEqual(native_row.schema_name, python_row.schema_name)
        self.assertEqual(native_row.id, python_row.id)
        self.assertEqual(native_row.data, python_row.data)

    @unittest.skipUnless(sbsv.native_available(), "native extension is unavailable")
    def test_native_backend_preserves_ignored_prefix_fields(self):
        parser = sbsv.parser()
        parser.ignore_prefix("[$timestamp] [$level]", save_ignored=True)
        parser.add_schema("[event] [value: int]")

        row = parser.loads("[2026-09-12 12:00:00] [INFO] [event] [value 3]\n")["event"][
            0
        ]

        self.assertEqual(row["$timestamp"], "2026-09-12 12:00:00")
        self.assertEqual(row["$level"], "INFO")
        self.assertEqual(row["value"], 3)

    def test_native_backend_falls_back_for_python_integer_syntax(self):
        parser = sbsv.parser()
        parser.add_schema("[data] [value: int]")

        row = parser.loads("[data] [value ١٢٣]\n")["data"][0]

        self.assertEqual(row["value"], 123)

    def test_native_backend_falls_back_for_custom_types(self):
        parser = sbsv.parser()
        parser.add_custom_type("hex", lambda value: int(value, 16))
        parser.add_schema("[data] [value: hex]")

        row = parser.loads("[data] [value ff]\n")["data"][0]

        self.assertEqual(row["value"], 255)

    def test_backends_reject_unmatched_closing_bracket(self):
        for use_native in (True, False):
            with self.subTest(use_native=use_native):
                parser = sbsv.parser(use_native=use_native)
                parser.add_schema("[data] [value: int]")
                with self.assertRaises(ValueError):
                    parser.loads("[data]] [value 1]\n")

    def test_native_backend_does_not_accept_extended_c_float_syntax(self):
        parser = sbsv.parser()
        parser.add_schema("[data] [value: float]")

        with self.assertRaises(ValueError):
            parser.loads("[data] [value nan(payload)]\n")
