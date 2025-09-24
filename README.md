Backend Lambda functions

- `backend/get_cafes/`: GET list of cafes by area (DynamoDB GSI `gsi_area`).
- `backend/upsert_cafes/`: Batch upsert cafes (POST with JSON list).

Packaging (local):

1) Create virtual environment and install deps if needed (boto3 is in AWS runtime by default):
   - No extra deps needed for these basic handlers.

2) TerraformがLambdaのzipを自動生成（`archive_file`）します。手動zipは不要です。

3) `infra/terraform` で `terraform init && terraform apply`。
