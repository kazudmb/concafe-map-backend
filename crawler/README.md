クローラー骨格（リーガルファースト）

- robots.txt とサイトの利用規約を順守して動作させる。
- サイトごとにプロバイダープラグインを差し込む構成です。

Example プロバイダー：

```
cd backend/crawler
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python main.py --provider example --area shinjuku --out ../../sample/cafes_shinjuku.json
```

ConCafe プロバイダー：

```
python -m crawler.main --provider concafe --area area02/pre08/sub040 --out concafe_sub040.json
```

`area` はデフォルトの `all` のままでも、`region/prefecture/area` 形式のスラッグを指定しても構いません（例：`area02`、`area02/pre08`、`area02/pre08/sub040`）。

- `area**` : 地域（エリア）
- `pre**` : 都道府県
- `sub**` : 市区町村・細分エリア