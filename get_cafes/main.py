import json
import os
import boto3
from boto3.dynamodb.conditions import Key

TABLE_NAME = os.environ.get("TABLE_NAME")
DEFAULT_AREA = os.environ.get("DEFAULT_AREA", "shinjuku")

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
    # HTTP API v2.0 event
    params = (event.get("queryStringParameters") or {})
    area = params.get("area") or DEFAULT_AREA

    try:
        # Query by GSI on area
        res = table.query(
            IndexName="gsi_area",
            KeyConditionExpression=Key("area").eq(area),
        )
        items = res.get("Items", [])
        return _response(200, items)
    except Exception as e:
        return _response(500, {"error": str(e)})

