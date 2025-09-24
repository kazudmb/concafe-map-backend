import json
import os
import boto3
import time
import base64

TABLE_NAME = os.environ.get("TABLE_NAME")
ddb = boto3.resource("dynamodb")
table = ddb.Table(TABLE_NAME)


def _response(status: int, body: dict | list):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, ensure_ascii=False),
    }


def handler(event, context):
    if event.get("isBase64Encoded"):
        body_str = base64.b64decode(event.get("body") or b"").decode("utf-8")
    else:
        body_str = event.get("body") or "[]"

    try:
        cafes = json.loads(body_str)
        now = int(time.time())
        with table.batch_writer() as batch:
            for c in cafes:
                item = {
                    "id": c["id"],
                    "name": c.get("name"),
                    "area": c.get("area", "shinjuku"),
                    "address": c.get("address"),
                    "lat": float(c["lat"]) if "lat" in c else None,
                    "lng": float(c["lng"]) if "lng" in c else None,
                    "hours": c.get("hours", ""),
                    "tags": c.get("tags", []),
                    "sourceUrl": c.get("sourceUrl", ""),
                    "updatedAt": c.get("updatedAt") or now,
                }
                batch.put_item(Item=item)
        return _response(200, {"ok": True, "count": len(cafes)})
    except Exception as e:
        return _response(400, {"error": str(e)})
