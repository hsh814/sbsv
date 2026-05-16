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
