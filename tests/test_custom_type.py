import unittest
import sbsv


class TestCustomType(unittest.TestCase):
    def test_custom_type_hex(self):
        p = sbsv.parser()
        p.add_custom_type("hex", lambda x: int(x, 16))
        p.add_schema("[data] [id: hex] [vals: list[hex]]")
        data = "[data] [id ff] [vals [a] [b] [10]]\n"
        result = p.loads(data)
        self.assertEqual(result["data"][0]["id"], 255)
        self.assertEqual(result["data"][0]["vals"], [10, 11, 16])

    def test_custom_types_are_parser_local(self):
        p1 = sbsv.parser()
        p1.add_custom_type("hex", lambda x: int(x, 16))
        p1.add_schema("[data] [id: hex]")

        p2 = sbsv.parser()
        with self.assertRaises(ValueError):
            p2.add_schema("[data] [id: hex]")

        p3 = sbsv.parser()
        p3.add_custom_type("hex", lambda x: f"custom-{x}")
        p3.add_schema("[data] [id: hex]")

        self.assertEqual(p1.loads("[data] [id ff]\n")["data"][0]["id"], 255)
        self.assertEqual(p3.loads("[data] [id ff]\n")["data"][0]["id"], "custom-ff")

    def test_body_parser_custom_types_are_local(self):
        parser = sbsv.body_parser(
            "[id: hex]", custom_types={"hex": lambda x: int(x, 16)}
        )
        self.assertEqual(parser.loads("[id ff]"), {"id": 255})

        with self.assertRaises(ValueError):
            sbsv.body_parser("[id: hex]")

    def test_custom_type_late_registration_rejected(self):
        p = sbsv.parser()
        with self.assertRaises(ValueError):
            p.add_schema("[d] [v: hex2]")

    def test_add_custom_type_after_schema_rejected(self):
        p = sbsv.parser()
        p.add_schema("[d] [v: str]")

        with self.assertRaises(ValueError):
            p.add_custom_type("hex3", lambda x: int(x, 16))

    def test_unknown_list_sub_type_rejected(self):
        p = sbsv.parser()

        with self.assertRaises(ValueError):
            p.add_schema("[d] [v: list[hex4]]")
