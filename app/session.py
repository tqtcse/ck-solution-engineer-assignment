from dataclasses import dataclass, field

from app import memory


@dataclass
class SessionState:
    session_id: str
    collected: dict = field(default_factory=dict)
    verified: bool = False
    customer_id: str | None = None
    orders_offered: list[str] = field(default_factory=list)
    failed_attempts: int = 0

    def missing(self) -> list[str]:
        return [f for f in ("email", "ssn_last4", "dob") if f not in self.collected]

    def save(self) -> None:
        memory.update_session(
            self.session_id,
            collected=self.collected,
            verified=self.verified,
            customer_id=self.customer_id,
            orders_offered=self.orders_offered,
            failed_attempts=self.failed_attempts,
        )


def get(session_id: str) -> SessionState:
    item = memory.get_session(session_id)
    return SessionState(
        session_id=session_id,
        collected=dict(item.get("collected") or {}),
        verified=bool(item.get("verified", False)),
        customer_id=item.get("customer_id"),
        orders_offered=list(item.get("orders_offered") or []),
        failed_attempts=int(item.get("failed_attempts", 0)),
    )
