from dataclasses import dataclass, field


@dataclass
class SessionState:
    session_id: str
    collected: dict = field(default_factory=dict)    
    verified: bool = False
    customer_id: str | None = None
    orders_offered: list[str] = field(default_factory=list)
    failed_attempts: int = 0
    messages: list = field(default_factory=list)      

    def missing(self) -> list[str]:
        return [f for f in ("email", "ssn_last4", "dob") if f not in self.collected]


_STORE: dict[str, SessionState] = {}      


def get(session_id: str) -> SessionState:
    return _STORE.setdefault(session_id, SessionState(session_id=session_id))