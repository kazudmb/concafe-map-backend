Crawler skeleton (legal-first)

- Respects robots.txt and site TOS (manual check required).
- Uses a provider plug-in per source site.
- Does not include actual target sites; fill providers only after legal review.

Run locally (example):

```
cd backend/crawler
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python main.py --provider example --area shinjuku --out ../../sample/cafes_shinjuku.json
```

