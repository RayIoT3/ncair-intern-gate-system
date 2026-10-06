"""Input rules. Everything that accepts user input goes through these functions."""
import re

from exceptions.custom_exceptions import (InvalidCardIDError, InvalidInternIDError,
                                          ValidationError)

INTERN_ID_RE = re.compile(r"NC-(NY|SI)-[0-9]{6}")          # NYSC / SIWES
CARD_ID_RE = re.compile(r"[0-9]{1,3}")
NAME_RE = re.compile(r"[A-Za-z][A-Za-z .'\-]{1,59}")
PHONE_RE = re.compile(r"(\+234|0)[0-9]{10}")
EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
SERIAL_NUMBER_RE = re.compile(r"[0-9]+")


def normalize_intern_id(text):
    """Strip every space and upper-case, so ' nc-ny-000101 ' becomes 'NC-NY-000101'."""
    return "".join(str(text or "").split()).upper()


def is_valid_intern_id(text):
    return INTERN_ID_RE.fullmatch(normalize_intern_id(text)) is not None


def validate_intern_id(text):
    iid = normalize_intern_id(text)
    if not iid:
        raise InvalidInternIDError("Enter an intern ID.")
    if not INTERN_ID_RE.fullmatch(iid):
        raise InvalidInternIDError("Expected NC-NY-###### (NYSC) or NC-SI-###### (SIWES).")
    return iid


def validate_card_id(value, max_card):
    """Accept 47, '47', '#47' or '047'; return the canonical three-digit form '047'."""
    text = str(value if value is not None else "").strip().lstrip("#").strip()
    if not CARD_ID_RE.fullmatch(text):
        raise InvalidCardIDError("Card numbers are digits, for example 047.")
    number = int(text)
    if not 1 <= number <= max_card:
        raise InvalidCardIDError(f"Card numbers run from 001 to {max_card:03d}.")
    return f"{number:03d}"


def validate_name(name):
    name = " ".join(str(name or "").split())
    if not NAME_RE.fullmatch(name):
        raise ValidationError("Name must be 2-60 characters: letters, spaces, . ' - only.")
    return name


def validate_department(department):
    department = " ".join(str(department or "").split())
    if not 2 <= len(department) <= 60:
        raise ValidationError("Department must be 2-60 characters.")
    return department


def validate_phone(phone):
    """Optional. Nigerian format: 08012345678 or +2348012345678."""
    phone = str(phone or "").replace(" ", "")
    if phone and not PHONE_RE.fullmatch(phone):
        raise ValidationError("Phone must look like 08012345678 or +2348012345678.")
    return phone


def validate_email(email):
    email = str(email or "").strip()
    if email and not EMAIL_RE.fullmatch(email):
        raise ValidationError("That email address does not look right.")
    return email


def validate_serial_number(value):
    """Accept an optional positive printed roster number and store it without leading zeroes."""
    text = str(value or "").strip()
    if not text:
        return None
    if not SERIAL_NUMBER_RE.fullmatch(text):
        raise ValidationError("Roster number must be a positive whole number.")
    normalized = text.lstrip("0")
    if not normalized:
        raise ValidationError("Roster number must be a positive whole number.")
    return normalized
