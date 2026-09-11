import json
from app import config, retrieval, verification
from app.session import SessionState

_CUST = json.loads((config.DATA / "customers.json").read_text(encoding="utf8"))
_ORD = json.loads((config.DATA / "orders.json").read_text(encoding="utf8"))

TOOL_SPECS = [
    {
        "toolSpec": {
            "name": "search_knowledge_base",
            "description": "Search internal company documents and SEC filings. Use for ALL questions "
                           "regarding company policies, business information, and figures in the 10-K report.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query in English"
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    },
    {
        "toolSpec": {
            "name": "submit_verification",
            "description": "Submit customer identity verification details. Call this as soon as the customer "
                           "provides ANY of the three items, one at a time. The server accumulates them and "
                           "replies with what is still needed. Pass verbatim user input.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "email": {"type": "string"},
                        "ssn_last4": {"type": "string"},
                        "dob": {
                            "type": "string",
                            "description": "Verbatim input, any natural date format"
                        }
                    },
                    "required": []
                }
            }
        }
    },
    {
        "toolSpec": {
            "name": "list_orders",
            "description": "List order IDs belonging to the currently verified customer.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        }
    },
    {
        "toolSpec": {
            "name": "get_order_status",
            "description": "Retrieve delivery and fulfillment status for a specific order ID.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string"}
                    },
                    "required": ["order_id"]
                }
            }
        }
    },
]


def _search_kb(args, _state):
    hits = retrieval.search(args.get("query", ""))
    if not hits or hits[0]["score"] < 0.3:      
        return {
            "results": [],
            "note": "No relevant content found in the knowledge base."
        }
    return {
        "results": [
            {"page": h["page"], "text": h["text"], "score": h["score"]}
            for h in hits
        ]
    }


def _submit_verification(args, state: SessionState):
    problems = []

    if args.get("email"):
        email, err = verification.parse_email(args["email"])
        problems.append(err) if err else state.collected.update(email=email)

    if args.get("ssn_last4"):
        ssn, err = verification.parse_ssn_last4(args["ssn_last4"])
        problems.append(err) if err else state.collected.update(ssn_last4=ssn)

    if args.get("dob"):
        dob, err = verification.parse_dob(args["dob"])
        if isinstance(dob, verification.Ambiguous):
            return {
                "verified": False,
                "need_clarification": "dob",
                "message": f"Date of birth '{args['dob']}' can be interpreted in two ways: "
                           f"{dob.first.isoformat()} or {dob.second.isoformat()}. "
                           "Please ask the customer to clarify which one is correct."
            }
        problems.append(err) if err else state.collected.update(dob=dob.isoformat())

    if problems:
        state.failed_attempts += 1
        return {"verified": False, "problems": problems}

    if state.missing():
        return {"verified": False, "still_needed": state.missing()}

    for c in _CUST:
        if all(c[k] == state.collected[k] for k in ("email", "ssn_last4", "dob")):
            state.verified = True
            state.customer_id = c["customer_id"]
            state.collected = {}
            return {"verified": True, "greeting_name": c["full_name"].split()[0]}

    state.failed_attempts += 1
    state.collected = {}
    return {
        "verified": False,
        "message": "Information does not match any record. Do not disclose which specific field was incorrect."
    }


def _list_orders(_args, state: SessionState):
    if not state.verified:                              
        return {
            "error": "NOT_VERIFIED",
            "message": "Verification is required before viewing orders."
        }
    ids = [o["order_id"] for o in _ORD if o["customer_id"] == state.customer_id]
    state.orders_offered = ids
    return {"order_ids": ids, "count": len(ids)}


def _get_order_status(args, state: SessionState):
    if not state.verified:                             
        return {
            "error": "NOT_VERIFIED",
            "message": "Verification is required before viewing order details."
        }
    oid = (args.get("order_id") or "").strip().upper()
    for o in _ORD:
        if o["order_id"].upper() == oid:
            if o["customer_id"] != state.customer_id:  
                return {
                    "error": "NOT_YOUR_ORDER",
                    "message": "This order ID does not belong to your verified account."
                }
            return {k: v for k, v in o.items() if k != "customer_id"}
    return {"error": "NOT_FOUND", "message": f"No order found with ID {oid}."}


_DISPATCH = {
    "search_knowledge_base": _search_kb,
    "submit_verification": _submit_verification,
    "list_orders": _list_orders,
    "get_order_status": _get_order_status,
}


def run_tool(name: str, args: dict, state: SessionState) -> dict:
    fn = _DISPATCH.get(name)
    if fn is None:
        return {"error": "UNKNOWN_TOOL", "name": name}
    try:
        return fn(args or {}, state)
    except Exception as exc:                            
        return {"error": "TOOL_FAILED", "detail": str(exc)[:200]}