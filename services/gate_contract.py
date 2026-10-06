"""Shared types and interface consumed by the gate screen."""
from dataclasses import dataclass
from typing import List, Optional, Protocol, Tuple, runtime_checkable


GateCandidate = Tuple[str, str, str, Optional[str], bool, Optional[str]]


@dataclass
class GateResult:
    kind: str
    title: str
    detail: str


@dataclass
class Movement:
    direction: str
    name: str
    intern_id: str
    at: str


@runtime_checkable
class GateScreenService(Protocol):
    def gate_candidates(self, query: str = "") -> List[GateCandidate]: ...
    def check_in(self, intern_id: str) -> GateResult: ...
    def check_out(self, intern_id: str) -> GateResult: ...
    def check_out_card_not_returned(self, intern_id: str) -> GateResult: ...
    def recent(self, limit: int = 6) -> List[Movement]: ...
