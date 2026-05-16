import os
import pathlib
import sys

import django

# Ensure project root is on sys.path
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.db import connection  # noqa: E402

cursor = connection.cursor()
cursor.execute(
    "SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;"
)
rows = cursor.fetchall()
for schema, name in rows:
    print(f"{schema}.{name}")
