# README — インフラ/バックエンド/フロント構成 & Lambda 実装ガイド（CI/CD サンプル付き・更新版）

> このREADMEは、本プロダクト群の**基本方針・命名規約・CI/CD**と、**Lambda（FastAPIなし）実装の型**をまとめたものです。  
> ご要望により、**コマンドは可能な限り1行**化し、**infraは同一Workflow内で plan/apply を別Step**に分けたサンプルに更新しました。

---

## 目次
- [全体像](#全体像)
- [レポジトリ構成（3リポ）](#レポジトリ構成3リポ)
- [命名規約 & 環境](#命名規約--環境)
- [CI/CD 方針](#cicd-方針)
- [GitHub Actions サンプル](#github-actions-サンプル)
  - [infra 用（plan→apply を同一Workflow内で分離）](#infra-用planapply-を同一workflow内で分離)
  - [backend 用（Python・直更新・1行コマンド）](#backend-用python直更新1行コマンド)
  - [frontend 用（S3 配信 & 最小 invalidate・1行コマンド）](#frontend-用s3-配信--最小-invalidate1行コマンド)
- [Lambda 実装ガイド（依存ゼロ版）](#lambda-実装ガイド依存ゼロ版)
- [デプロイ手順（backend 手動時の参考）](#デプロイ手順backend-手動時の参考)
- [フロント配信のキャッシュ戦略](#フロント配信のキャッシュ戦略)
- [よくある拡張・分割のタイミング](#よくある拡張分割のタイミング)
- [最低限のIAM（目安）](#最低限のiam目安)

---

## 全体像
- **目的**：CloudFront/S3/API Gateway/Lambda の“受け皿”を**インフラで固定**し、以後は**バックエンド/フロントを高速に更新**できる構成を作る。
- **ポイント**：
  - 環境は **`dev` / `stg` / `prd`**。
  - **Lambda のエイリアス名は `live` で固定**（全環境共通）。
  - **インフラは構成変更時のみ**。アプリは `main` マージで**自動デプロイ**。

---

## レポジトリ構成（3リポ）

### 1) `{product}-infra`
- 役割：Terraformで“受け皿”を作成（API Gateway、Lambda本体＋`live` エイリアス、S3、CloudFront など）
- ディレクトリ指針：
  ```
  infra/
    app/
      dev/
      stg/
      prd/
    modules/
      api_gateway_lambda/
      s3_cloudfront/
  ```
- ルール：`main.tf` は**module呼び出し専用**にし、肥大化させない（実装は `modules/` に分割）

### 2) `{product}-backend`
- 役割：**Lambda コード（Python）**
- デプロイ：`main` マージ → **ビルド → S3 アップ → `update-function-code` → `publish-version` → `update-alias live`**

### 3) `{product}-frontend`
- 役割：フロント（Node / React / TypeScript / Tailwind CSS / shadcn/ui）
- デプロイ：`main` マージ → **ビルド → S3 sync/put → CloudFront invalidate（最小）**

---

## CI/CD 方針

### infra
- トリガ：`main` マージ
- アクション：`terraform fmt/validate/plan` → **保存した plan を apply**（同一Workflow内で別Step）

### backend
- トリガ：`main` マージ
- アクション：
  1. 依存インストール → **zip作成**
  2. **S3** に`build.zip`をアップロード（`lambda/{product}-api-{env}/${GITHUB_SHA}.zip`）
  3. `aws lambda update-function-code`（$LATEST更新）
  4. `aws lambda publish-version`（不変版を確定）
  5. `aws lambda update-alias --name live --function-version <Version>`（入口を新Verに）

> ロールバック：`aws lambda update-alias --name live --function-version <旧版>` で即時戻し

### frontend
- トリガ：`main` マージ
- アクション：
  1. `npm ci && npm run build`（静的出力）
  2. **S3 へアップロード**（HTML短期/アセット長期の Cache-Control を付与）
  3. **CloudFront invalidate** は最小（`/index.html` と `/`）

---

## GitHub Actions サンプル

> それぞれ **`.github/workflows/*.yml`** に配置してください。  
> OIDC AssumeRole 前提で、Role ARN やバケット/ディストリビューションIDは **環境ごとの Secrets/Variables** に入れて参照します。

### infra 用（plan→apply を同一Workflow内で分離）
`.github/workflows/infra-apply.yml`
```yaml
name: infra-apply
on:
  push:
    branches: [ main ]
    paths: [ "infra/**" ]

jobs:
  apply:
    runs-on: ubuntu-latest
    permissions: { id-token: write, contents: read }
    strategy:
      matrix: { env: [dev, stg, prd] }

    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets['AWS_ROLE_ARN_' + matrix.env.upper()] }}
          aws-region: ${{ vars.AWS_REGION || 'ap-northeast-1' }}

      - name: Terraform Init / Fmt / Validate
        working-directory: infra/app/${{ matrix.env }}
        run: |
          terraform init -input=false
          terraform fmt -check
          terraform validate

      - name: Terraform Plan (保存)
        id: plan
        working-directory: infra/app/${{ matrix.env }}
        run: terraform plan -out=plan.bin -input=false

      - name: Terraform Apply（保存したplanを適用）
        if: ${{ success() }}
        working-directory: infra/app/${{ matrix.env }}
        run: terraform apply -auto-approve -input=false plan.bin
```

### backend 用（Python・直更新・1行コマンド）
`.github/workflows/backend-deploy.yml`
```yaml
name: backend-deploy
on:
  push:
    branches: [ main ]
    paths: [ "src/**", "requirements.txt", ".github/workflows/backend-deploy.yml" ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions: { id-token: write, contents: read }
    strategy:
      matrix: { env: [dev, stg, prd] }
    env:
      AWS_REGION: ${{ vars.AWS_REGION || 'ap-northeast-1' }}
      PRODUCT: ${{ vars.PRODUCT }}   # 例: sns
      FUNC_BASE: api

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }

      - name: Build zip
        run: |
          pip install -r requirements.txt -t build_dir || true
          cp -R src/* build_dir/
          (cd build_dir && zip -r ../build.zip .)

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets['AWS_ROLE_ARN_' + matrix.env.upper()] }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Upload artifact to S3
        run: |
          ARTIFACT_BUCKET=${{ secrets['ARTIFACT_BUCKET_' + matrix.env.upper()] }}
          KEY=lambda/${{ env.PRODUCT }}-${{ env.FUNC_BASE }}-${{ matrix.env }}/${{ github.sha }}.zip
          aws s3 cp build.zip s3://$ARTIFACT_BUCKET/$KEY
          echo "ARTIFACT_BUCKET=$ARTIFACT_BUCKET" >> $GITHUB_ENV
          echo "ARTIFACT_KEY=$KEY" >> $GITHUB_ENV

      - name: Update Lambda → Publish → Alias switch（全部1行）
        run: |
          FUNC="${{ env.PRODUCT }}-${{ env.FUNC_BASE }}-${{ matrix.env }}"
          aws lambda update-function-code --function-name "$FUNC" --s3-bucket "$ARTIFACT_BUCKET" --s3-key "$ARTIFACT_KEY"
          VER=$(aws lambda publish-version --function-name "$FUNC" --query Version --output text)
          aws lambda update-alias --function-name "$FUNC" --name live --function-version "$VER"
```

### frontend 用（S3 配信 & 最小 invalidate・1行コマンド）
`.github/workflows/frontend-deploy.yml`
```yaml
name: frontend-deploy
on:
  push:
    branches: [ main ]
    paths: [ "src/**", "package.json", "package-lock.json", "next.config.*", ".github/workflows/frontend-deploy.yml" ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions: { id-token: write, contents: read }
    strategy:
      matrix: { env: [dev, stg, prd] }
    env:
      AWS_REGION: ${{ vars.AWS_REGION || 'ap-northeast-1' }}
      NEXT_PUBLIC_API_BASE_URL: ${{ vars['NEXT_PUBLIC_API_BASE_URL_' + matrix.env.upper()] }}

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }

      - name: Install & Build
        run: |
          npm ci
          npm run build

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets['AWS_ROLE_ARN_' + matrix.env.upper()] }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Upload assets (immutable) — 1行
        run: |
          FRONT_BUCKET=${{ secrets['FRONT_BUCKET_' + matrix.env.upper()] }}
          aws s3 cp out/ s3://$FRONT_BUCKET/ --recursive --exclude "*.html" --cache-control "public,max-age=31536000,immutable" --metadata-directive REPLACE

      - name: Upload HTML (short cache) — 1行
        run: |
          FRONT_BUCKET=${{ secrets['FRONT_BUCKET_' + matrix.env.upper()] }}
          aws s3 cp out/ s3://$FRONT_BUCKET/ --recursive --exclude "*" --include "*.html" --cache-control "public,max-age=60,must-revalidate" --metadata-directive REPLACE

      - name: Invalidate minimal paths — 1行
        run: |
          CF_ID=${{ secrets['CF_DISTRIBUTION_ID_' + matrix.env.upper()] }}
          aws cloudfront create-invalidation --distribution-id "$CF_ID" --paths "/index.html" "/"
```

---

## Lambda 実装ガイド（依存ゼロ版）

> **FastAPI なし**でスッキリ保つ型。ハンドラは“入口だけ”、実処理は**ルーター＋ドメイン別ファイル**に分割。

### ディレクトリ（例）
```
{product}-backend/
  src/
    app/
      handlers/
        lambda_handler.py      # Lambda入口（超薄い）
      router.py                # ルーティング（メソッド/パスで振り分け）
      http.py                  # JSONレスポンス等ヘルパ
      routes/
        users.py               # /users 系
        # posts.py ... 必要に応じて追加
  requirements.txt             # 初期は空でもOK
```

### Terraform 側の handler 設定
- `handler = "app.handlers.lambda_handler.lambda_handler"`

### 最小コード例
`src/app/http.py`
```python
import json
def json_ok(body: dict, status: int = 200):
    return {"statusCode": status, "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body, ensure_ascii=False)}
def json_error(message: str, status: int = 400):
    return json_ok({"error": message}, status)
```

`src/app/routes/users.py`
```python
from ..http import json_ok
def list_users(event, ctx): return json_ok({"users": []})
def create_user(event, ctx): return json_ok({"id": "u_123"}, 201)
def get_user(event, ctx, id: str): return json_ok({"id": id})
```

`src/app/router.py`
```python
import re
from typing import Callable, Any, List, Tuple
from .routes import users

Route = Tuple[str, re.Pattern, Callable[..., Any]]
ROUTES: List[Route] = [
    ("GET",  re.compile(r"^/users$"),               users.list_users),
    ("POST", re.compile(r"^/users$"),               users.create_user),
    ("GET",  re.compile(r"^/users/(?P<id>[^/]+)$"), users.get_user),
]

def dispatch(method: str, path: str, event, ctx):
    for m, pattern, handler in ROUTES:
        if m == method:
            mobj = pattern.match(path)
            if mobj:
                return handler(event, ctx, **mobj.groupdict())
    return {"statusCode": 404, "body": "Not Found"}
```

`src/app/handlers/lambda_handler.py`
```python
from ..router import dispatch

def lambda_handler(event, context):
    method = event["requestContext"]["http"]["method"]  # HTTP API (v2)想定
    path   = event.get("rawPath", "/")
    try:
        return dispatch(method, path, event, context)
    except Exception:
        return {"statusCode": 500, "body": "Internal Server Error"}
```

### ルート追加手順
1. `routes/xxx.py` に関数を追加  
2. `router.py` の `ROUTES` に1行追加（`("METHOD", r"^/path$", handler)`）

---

## デプロイ手順（backend 手動時の参考）
> Actions が使えない/検証したいときのメモ。

```bash
# 1) zip
pip install -r requirements.txt -t build_dir && cp -R src/* build_dir/ && (cd build_dir && zip -r ../build.zip .)

# 2) S3へ
aws s3 cp build.zip s3://<ARTIFACT_BUCKET>/<KEY>

# 3) $LATEST更新 → 4) version発行 → 5) alias切替
aws lambda update-function-code --function-name {product}-api-{env} --s3-bucket <ARTIFACT_BUCKET> --s3-key <KEY>
VER=$(aws lambda publish-version --function-name {product}-api-{env} --query Version --output text)
aws lambda update-alias --function-name {product}-api-{env} --name live --function-version $VER
```

---

## フロント配信のキャッシュ戦略
- **アセット（*.js, *.css, 画像等）**：ハッシュ付きファイル名＋  
  `Cache-Control: public,max-age=31536000,immutable`
- **HTML（*.html）**：  
  `Cache-Control: public,max-age=60,must-revalidate`
- **Invalidation**：毎回 **`/index.html` と `/`** のみ（最小）。  
  アセットはハッシュ名なので invalidate 不要。

---

## よくある拡張・分割のタイミング
- ルートやLOCが増え**読みづらい**、Zipが**肥大**、**メモリ/タイムアウト**を分けたい  
→ **ドメイン単位で Lambda を分割**（例：`{product}-users-api-{env}` / `{product}-posts-api-{env}`）  
→ API Gateway の該当パスだけ新関数に紐付け替え

- S3/SQS/定時など**非同期トリガ**  
→ 関数名にトリガを付与（例：`{product}-image-resize-s3-{env}`、`{product}-mailer-sqs-{env}`）

---

## 最低限のIAM（目安）

**backendデプロイ（OIDC AssumeRole）**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow",
      "Action": ["lambda:UpdateFunctionCode","lambda:PublishVersion","lambda:UpdateAlias","lambda:GetFunction","lambda:ListVersionsByFunction"],
      "Resource": "arn:aws:lambda:ap-northeast-1:<ACCOUNT_ID>:function:{product}-api-*"
    },
    { "Effect": "Allow",
      "Action": ["s3:PutObject","s3:GetObject","s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::<ARTIFACT_BUCKET_DEV>",
        "arn:aws:s3:::<ARTIFACT_BUCKET_DEV>/*",
        "arn:aws:s3:::<ARTIFACT_BUCKET_STG>",
        "arn:aws:s3:::<ARTIFACT_BUCKET_STG>/*",
        "arn:aws:s3:::<ARTIFACT_BUCKET_PRD>",
        "arn:aws:s3:::<ARTIFACT_BUCKET_PRD>/*"
      ]
    }
  ]
}
```

**frontendデプロイ**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect":"Allow",
      "Action": ["s3:PutObject","s3:DeleteObject","s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::<FRONT_BUCKET_DEV>",
        "arn:aws:s3:::<FRONT_BUCKET_DEV>/*",
        "arn:aws:s3:::<FRONT_BUCKET_STG>",
        "arn:aws:s3:::<FRONT_BUCKET_STG>/*",
        "arn:aws:s3:::<FRONT_BUCKET_PRD>",
        "arn:aws:s3:::<FRONT_BUCKET_PRD>/*"
      ]
    },
    { "Effect":"Allow", "Action":["cloudfront:CreateInvalidation"], "Resource":"*" }
  ]
}
```

---

### 最後に
- **小さく始めて、綺麗に育てる**：最初は `*-api-*` 1本 → コードはファイル分割 → 必要に応じて**ドメイン分割**。  
- ルール（命名・CI・エイリアス`live`固定）を守れば、**量産しても崩れません**。
