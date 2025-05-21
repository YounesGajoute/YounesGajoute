# database/calibration_db.py

import sqlite3
from datetime import datetime
from typing import List, Optional
import numpy as np
from dataclasses import dataclass
import os

DEFAULT_DB_PATH = "/home/Bot/Desktop/techmac_calibration.db"
FALLBACK_DB_PATH = os.path.join(os.path.dirname(__file__), "../../data/techmac_calibration.db")


@dataclass
class CalibrationPoint:
    pressure: float
    voltage: float
    timestamp: datetime


@dataclass
class CalibrationResult:
    chamber_id: int
    multiplier: float
    offset: float
    r_squared: float
    calibration_date: datetime
    points: List[CalibrationPoint]


class CalibrationDatabase:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = DEFAULT_DB_PATH

            # Try to ensure the parent directory exists
            try:
                os.makedirs(os.path.dirname(db_path), exist_ok=True)
                # Try creating the file to test write access
                open(db_path, 'a').close()
            except Exception:
                print(f"⚠️ Falling back to local DB path: {FALLBACK_DB_PATH}")
                db_path = os.path.abspath(FALLBACK_DB_PATH)
                os.makedirs(os.path.dirname(db_path), exist_ok=True)

        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS calibration_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chamber_id INTEGER NOT NULL,
                    multiplier REAL NOT NULL,
                    offset REAL NOT NULL,
                    r_squared REAL NOT NULL,
                    calibration_date TIMESTAMP NOT NULL,
                    is_active BOOLEAN DEFAULT 1
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS calibration_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    calibration_id INTEGER NOT NULL,
                    pressure REAL NOT NULL,
                    voltage REAL NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    FOREIGN KEY (calibration_id) REFERENCES calibration_records(id)
                )
            ''')
            conn.commit()

    def save_calibration(self, calibration: CalibrationResult):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE calibration_records
                SET is_active = 0
                WHERE chamber_id = ? AND is_active = 1
            ''', (calibration.chamber_id,))

            cursor.execute('''
                INSERT INTO calibration_records
                (chamber_id, multiplier, offset, r_squared, calibration_date, is_active)
                VALUES (?, ?, ?, ?, ?, 1)
            ''', (
                calibration.chamber_id,
                calibration.multiplier,
                calibration.offset,
                calibration.r_squared,
                calibration.calibration_date.isoformat()
            ))

            calibration_id = cursor.lastrowid

            for point in calibration.points:
                cursor.execute('''
                    INSERT INTO calibration_points
                    (calibration_id, pressure, voltage, timestamp)
                    VALUES (?, ?, ?, ?)
                ''', (
                    calibration_id,
                    point.pressure,
                    point.voltage,
                    point.timestamp.isoformat()
                ))

            conn.commit()

    def get_active_calibration(self, chamber_id: int) -> Optional[CalibrationResult]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, multiplier, offset, r_squared, calibration_date
                FROM calibration_records
                WHERE chamber_id = ? AND is_active = 1
                ORDER BY calibration_date DESC
                LIMIT 1
            ''', (chamber_id,))
            record = cursor.fetchone()

            if not record:
                return None

            cursor.execute('''
                SELECT pressure, voltage, timestamp
                FROM calibration_points
                WHERE calibration_id = ?
                ORDER BY timestamp
            ''', (record[0],))
            points = [
                CalibrationPoint(pressure=row[0], voltage=row[1], timestamp=datetime.fromisoformat(row[2]))
                for row in cursor.fetchall()
            ]

            return CalibrationResult(
                chamber_id=chamber_id,
                multiplier=record[1],
                offset=record[2],
                r_squared=record[3],
                calibration_date=datetime.fromisoformat(record[4]),
                points=points
            )

    def get_calibration_history(self, chamber_id: int, limit: int = 10) -> List[CalibrationResult]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, multiplier, offset, r_squared, calibration_date
                FROM calibration_records
                WHERE chamber_id = ?
                ORDER BY calibration_date DESC
                LIMIT ?
            ''', (chamber_id, limit))

            results = []
            for record in cursor.fetchall():
                cursor.execute('''
                    SELECT pressure, voltage, timestamp
                    FROM calibration_points
                    WHERE calibration_id = ?
                    ORDER BY timestamp
                ''', (record[0],))
                points = [
                    CalibrationPoint(pressure=row[0], voltage=row[1], timestamp=datetime.fromisoformat(row[2]))
                    for row in cursor.fetchall()
                ]
                results.append(CalibrationResult(
                    chamber_id=chamber_id,
                    multiplier=record[1],
                    offset=record[2],
                    r_squared=record[3],
                    calibration_date=datetime.fromisoformat(record[4]),
                    points=points
                ))
            return results

    def calculate_calibration(self, chamber_id: int, points: List[CalibrationPoint]) -> CalibrationResult:
        if len(points) < 2:
            raise ValueError("At least two calibration points required")

        x = np.array([p.voltage for p in points])
        y = np.array([p.pressure for p in points])

        x_mean = np.mean(x)
        y_mean = np.mean(y)
        multiplier = np.sum((x - x_mean) * (y - y_mean)) / np.sum((x - x_mean) ** 2)
        offset = y_mean - multiplier * x_mean
        y_pred = multiplier * x + offset
        r_squared = 1 - np.sum((y - y_pred) ** 2) / np.sum((y - y_mean) ** 2)

        return CalibrationResult(
            chamber_id=chamber_id,
            multiplier=multiplier,
            offset=offset,
            r_squared=r_squared,
            calibration_date=datetime.now(),
            points=points
        )
