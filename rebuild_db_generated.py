#! /usr/bin/env python3

# Script to rebuild the LogsGenerated table which caches values from the log files

import sqlite3 as lite
import sys
import os

from plot_app.config import get_db_filename
from tornado_handlers.common import generate_db_data_from_log_file

with lite.connect(get_db_filename()) as con:
    cur = con.cursor()
    cur.execute("SELECT id FROM logs")
    logs_ids = cur.fetchall()

    for i, (log_id,) in enumerate(logs_ids):
        print(f"[{i+1}/{len(logs_ids)}] Updating {log_id}")
        generate_db_data_from_log_file(log_id, con)
