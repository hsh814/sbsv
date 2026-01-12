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

    def test_custom_type_late_registration(self):
        p = sbsv.parser()
        p.add_schema("[d] [v: hex2]")
        # Register after schema
        p.add_custom_type("hex2", lambda x: int(x, 16))
        result = p.loads("[d] [v 1a]\n")
        self.assertEqual(result["d"][0]["v"], 26)
