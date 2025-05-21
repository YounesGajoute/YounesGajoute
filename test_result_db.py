# database/test_result_db.py

import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

from multi_chamber_test.core.roles import get_current_username

# You can customize this path or pull it from your constants
DEFAULT_DB_PATH = os.path.expanduser("~/multi_chamber_test/data/test_results.db")
MAX_RECORDS = 1000

class TestResultDatabase:
    """
    Rotating SQLite store for test results.
    Keeps only the last MAX_RECORDS runs.
    """

    def __init__(self, db_path: Optional[str] = None, max_records: int = MAX_RECORDS):
        if db_path is None:
            db_path = DEFAULT_DB_PATH
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.max_records = max_records
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Table for overall test runs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS test_results (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp      TEXT    NOT NULL,
                    operator_id    TEXT,
                    reference      TEXT,
                    test_mode      TEXT,
                    test_duration  INTEGER,
                    overall_result INTEGER
                )
            """)
            # Table for per-chamber results
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chamber_results (
                    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_id            INTEGER NOT NULL,
                    chamber_id         INTEGER,
                    enabled            INTEGER,
                    pressure_target    REAL,
                    pressure_threshold REAL,
                    pressure_tolerance REAL,
                    final_pressure     REAL,
                    result             INTEGER,
                    FOREIGN KEY(test_id) REFERENCES test_results(id)
                )
            """)
            conn.commit()

    def save_test_result(self, record: Dict[str, Any]):
        """
        Insert a new test run plus its chamber data, then trim old runs.
        `record` should match the dict passed to TestLogger.log_test_result:
          {
            'timestamp': ISO8601 string,
            'reference': str,
            'test_mode': str,
            'test_duration': int,
            'overall_result': bool,
            'chambers': [
                {
                  'chamber_id': int,
                  'enabled': bool,
                  'pressure_target': float,
                  'pressure_threshold': float,
                  'pressure_tolerance': float,
                  'final_pressure': float,
                  'result': bool
                },
                ...
            ]
          }
        """
        operator = get_current_username() or "N/A"
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Insert overall test
            cursor.execute("""
                INSERT INTO test_results
                  (timestamp, operator_id, reference, test_mode, test_duration, overall_result)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                record['timestamp'],
                operator,
                record.get('reference'),
                record.get('test_mode'),
                record.get('test_duration'),
                1 if record.get('overall_result') else 0
            ))
            test_id = cursor.lastrowid

            # Insert each chamber
            for ch in record.get('chambers', []):
                cursor.execute("""
                    INSERT INTO chamber_results
                      (test_id, chamber_id, enabled, pressure_target,
                       pressure_threshold, pressure_tolerance,
                       final_pressure, result)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    test_id,
                    ch.get('chamber_id'),
                    1 if ch.get('enabled') else 0,
                    ch.get('pressure_target'),
                    ch.get('pressure_threshold'),
                    ch.get('pressure_tolerance'),
                    ch.get('final_pressure'),
                    1 if ch.get('result') else 0
                ))

            # Rotate: delete oldest if we exceed max_records
            cursor.execute("SELECT COUNT(*) FROM test_results")
            total = cursor.fetchone()[0]
            if total > self.max_records:
                overflow = total - self.max_records
                cursor.execute(f"""
                    DELETE FROM test_results
                    WHERE id IN (
                        SELECT id FROM test_results
                        ORDER BY timestamp ASC
                        LIMIT ?
                    )
                """, (overflow,))
                # cascade delete chamber_results of those runs
                cursor.execute("PRAGMA foreign_keys = ON")

            conn.commit()

    def get_all_results(self) -> List[Dict[str, Any]]:
        """
        Fetch every stored test run (oldest first) as a list of dicts:
        {
          'id', 'timestamp', 'operator_id', 'reference', 'test_mode',
          'test_duration', 'overall_result', 'chambers': [ {...}, ... ]
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM test_results ORDER BY timestamp ASC")
            rows = cursor.fetchall()
            results = []
            for row in rows:
                test_id, ts, op, ref, mode, dur, overall = row
                cursor.execute("""
                    SELECT chamber_id, enabled, pressure_target,
                           pressure_threshold, pressure_tolerance,
                           final_pressure, result
                      FROM chamber_results
                     WHERE test_id = ?
                     ORDER BY chamber_id
                """, (test_id,))
                chambers = []
                for c in cursor.fetchall():
                    chambers.append({
                        'chamber_id':    c[0],
                        'enabled':       bool(c[1]),
                        'pressure_target':    c[2],
                        'pressure_threshold': c[3],
                        'pressure_tolerance': c[4],
                        'final_pressure':     c[5],
                        'result':         bool(c[6])
                    })
                results.append({
                    'id':             test_id,
                    'timestamp':      ts,
                    'operator_id':    op,
                    'reference':      ref,
                    'test_mode':      mode,
                    'test_duration':  dur,
                    'overall_result': bool(overall),
                    'chambers':       chambers
                })
            return results
