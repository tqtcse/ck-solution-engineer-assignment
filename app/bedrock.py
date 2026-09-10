import json
from functools import lru_cache
import boto3
from app import config


@lru_cache(maxsize=1)
def client():
    return boto3.client("bedrock-runtime", region_name=config.AWS_REGION)


def embed(text: str) -> list[float]:
    body = json.dumps({
        "inputText": text,
        "dimensions": config.EMBED_DIM,
        "normalize": True,
    })
    resp = client().invoke_model(modelId=config.EMBED_MODEL, body=body)
    return json.loads(resp["body"].read())["embedding"]
