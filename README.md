# PolicyEdge

## Setup

1. `pip install -r requirements.txt`
2. Copy `.env.example` → `.env` and fill in the values
3. Set `DATABASE_URL` (Postgres)
4. Create the schema: `python setup_db.py`
5. Run: `flask run` or `gunicorn PolicyEdge:app`