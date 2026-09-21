import os
import sys

# Ensure parent project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set VERCEL environment variable
os.environ['VERCEL'] = '1'

import database
import shutil

# In Vercel serverless environment, local filesystem is read-only.
# Copy seeded market.db to /tmp/market.db so SQLite can write
tmp_db = '/tmp/market.db'
seed_db = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'market.db')

if not os.path.exists(tmp_db):
    if os.path.exists(seed_db):
        try:
            shutil.copyfile(seed_db, tmp_db)
        except Exception:
            database.DB_PATH = tmp_db
            database.init_db()
    else:
        database.DB_PATH = tmp_db
        database.init_db()

database.DB_PATH = tmp_db

from app import app
