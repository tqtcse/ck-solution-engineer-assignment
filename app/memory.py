import time
import uuid
from functools import lru_cache

import boto3
from boto3.dynamodb.conditions import Key

from app import config
from app.obs import redact

TTL_DAYS = 30


@lru_cache(maxsize=1)
def _table():
    return boto3.resource("dynamodb", region_name=config.AWS_REGION).Table(config.CONV_TABLE)


def _expires_at() -> int:
    return int(time.time()) + TTL_DAYS * 86400


def append_message(session_id: str, role: str, content: str, **meta) -> None:
    now_ms = int(time.time() * 1000)
    item = {
        "pk": f"SESS#{session_id}",
        "sk": f"MSG#{now_ms:013d}#{uuid.uuid4().hex[:6]}",
        "role": role,
        "content": redact(content),
        "created_at": now_ms,
        "expires_at": _expires_at(),
    }
    item.update({k: v for k, v in meta.items() if v is not None})
    _table().put_item(Item=item)


def load_recent(session_id: str, n: int | None = None) -> list[dict]:
    resp = _table().query(
        KeyConditionExpression=Key("pk").eq(f"SESS#{session_id}") & Key("sk").begins_with("MSG#"),
        ScanIndexForward=False,
        Limit=n or config.HISTORY_TURNS,
    )
    return [{"role": i["role"], "content": i["content"]} for i in reversed(resp["Items"])]


def get_session(session_id: str) -> dict:
    resp = _table().get_item(Key={"pk": f"SESS#{session_id}", "sk": "META"})
    return resp.get("Item", {})


def update_session(session_id: str, **fields) -> None:
    fields["last_activity_at"] = int(time.time())
    fields["expires_at"] = _expires_at()

    names, values, sets = {}, {}, []
    for i, (key, value) in enumerate(fields.items()):
        names[f"#f{i}"] = key
        values[f":v{i}"] = value
        sets.append(f"#f{i} = :v{i}")

    _table().update_item(
        Key={"pk": f"SESS#{session_id}", "sk": "META"},
        UpdateExpression="SET " + ", ".join(sets),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )