import unittest

from exceptions.custom_exceptions import InvalidCardIDError, InvalidInternIDError, ValidationError
from validation import validators as v


class ValidationTests(unittest.TestCase):
    def test_valid_ids(self):
        for text in ("NC-NY-000101", "nc-si-000114", " NC-NY-000101 ", "NC - SI - 000114"):
            self.assertTrue(v.is_valid_intern_id(text), text)

    def test_invalid_ids(self):
        for text in ("ABC!!!!!123", "", "NC-XX-000101", "NC-NY-00010", "NC-NY-0001011", "NC-NY-00010A", None):
            self.assertFalse(v.is_valid_intern_id(text), text)
            with self.assertRaises(InvalidInternIDError):
                v.validate_intern_id(text)

    def test_normalize(self):
        self.assertEqual(v.validate_intern_id(" nc-ny-000101 "), "NC-NY-000101")

    def test_card_ids(self):
        for raw in (47, "47", "#47", "047", " 047 "):
            self.assertEqual(v.validate_card_id(raw, 60), "047")
        for raw in ("0", "61", "abc", "", None, "1234", "-3", "4.5"):
            with self.assertRaises(InvalidCardIDError):
                v.validate_card_id(raw, 60)

    def test_names_phone_email(self):
        self.assertEqual(v.validate_name("  Amina   Yusuf "), "Amina Yusuf")
        with self.assertRaises(ValidationError):
            v.validate_name("R2D2!!")
        self.assertEqual(v.validate_phone("0801 234 5678"), "08012345678")
        self.assertEqual(v.validate_phone(""), "")
        with self.assertRaises(ValidationError):
            v.validate_phone("12345")
        with self.assertRaises(ValidationError):
            v.validate_email("not-an-email")

    def test_serial_numbers(self):
        self.assertIsNone(v.validate_serial_number(""))
        self.assertEqual(v.validate_serial_number("001"), "1")
        for value in ("0", "-1", "one", "1.5"):
            with self.assertRaises(ValidationError):
                v.validate_serial_number(value)


if __name__ == "__main__":
    unittest.main()
