"""Every controlled error in the system. Each one carries what the GUI needs to show it:
`kind` is "er" (error) or "wa" (warning) and `title` is the short heading."""


class GateError(Exception):
    kind = "er"
    title = "Error"

    def __init__(self, message=None):
        super().__init__(message or self.title)


# ---- input -----------------------------------------------------------------
class ValidationError(GateError):
    title = "Invalid input"


class InvalidInternIDError(ValidationError):
    title = "Invalid ID format"


class InvalidCardIDError(ValidationError):
    title = "Invalid card number"


# ---- records ---------------------------------------------------------------
class RecordNotFoundError(GateError):
    title = "Record not found"


class InternNotFoundError(RecordNotFoundError):
    title = "ID not found"


class CardNotFoundError(RecordNotFoundError):
    title = "Card not found"


class DuplicateInternError(GateError):
    title = "Intern already registered"


class DuplicateSerialNumberError(GateError):
    title = "Roster number already assigned"


# ---- gate operations -------------------------------------------------------
class DuplicateCheckInError(GateError):
    kind = "wa"
    title = "Already inside"


class NotCheckedInError(GateError):
    kind = "wa"
    title = "Not checked in"


# ---- guest cards -----------------------------------------------------------
class CardUnavailableError(GateError):
    title = "Card unavailable"


class NoCardsAvailableError(CardUnavailableError):
    title = "No guest cards left"


class InvalidCardOperationError(GateError):
    title = "Invalid card operation"


# ---- infrastructure --------------------------------------------------------
class StorageError(GateError):
    title = "Storage problem"


class CorruptFileError(StorageError):
    title = "Corrupted data file"


class ExternalAPIError(GateError):
    title = "External service unavailable"


class AIServiceError(GateError):
    title = "AI unavailable"
