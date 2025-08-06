import sqlite3
import os
from typing import List, Dict, Any, Optional
from config.settings import get_settings

settings = get_settings()

class Database:
    def __init__(self, db_path: str = settings.DB_PATH):
        self.db_path = db_path
        if self.db_path != ':memory:':
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        # Connect to the database, allowing multi-threaded access for Streamlit
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        """Creates all necessary tables with the correct schema."""
        if not self.conn:
            return
        cursor = self.conn.cursor()
        
        # Correct schema for the stocks table, including the 'symbol' column
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS stocks (
            ts_code TEXT PRIMARY KEY,
            symbol TEXT,
            name TEXT,
            industry TEXT,
            list_date TEXT,
            region TEXT
        )
        ''')

        # Correct schema for the indices table, using 'ts_code' as the primary key
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS indices (
            ts_code TEXT PRIMARY KEY,
            name TEXT
        )
        ''')

        # Watchlist for stocks
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS watchlist (
            ts_code TEXT PRIMARY KEY,
            name TEXT,
            add_date TEXT,
            in_pool INTEGER DEFAULT 0
        )
        ''')

        # Watchlist for indices
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS index_watchlist (
            ts_code TEXT PRIMARY KEY,
            name TEXT,
            add_date TEXT,
            in_pool INTEGER DEFAULT 0
        )
        ''')

        # Daily price data for stocks
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_price (
            ts_code TEXT,
            date TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            turnover REAL,
            PRIMARY KEY (ts_code, date)
        )
        ''')

        # Daily price data for indices
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS index_daily_price (
            ts_code TEXT,
            date TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            turnover REAL,
            PRIMARY KEY (ts_code, date)
        )
        ''')

        # Other tables...
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS fundamentals (
            ts_code TEXT,
            report_date TEXT,
            pe_ttm REAL,
            pb REAL,
            total_mv REAL,
            PRIMARY KEY (ts_code, report_date)
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            portfolio_name TEXT,
            ts_code TEXT,
            side TEXT,
            price REAL,
            qty REAL,
            fee REAL
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            strategy TEXT,
            ts_code TEXT,
            date TEXT,
            signal_type TEXT,
            PRIMARY KEY (strategy, ts_code, date, signal_type)
        )
        ''')

        # Portfolio table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS portfolio (
            portfolio_name TEXT,
            ts_code TEXT,
            qty REAL,
            cost REAL,
            PRIMARY KEY (portfolio_name, ts_code)
        )
        ''')

        self.conn.commit()

    def execute(self, query: str, params: tuple = None) -> None:
        """执行SQL语句"""
        cursor = self.conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        self.conn.commit()

    def executemany(self, query: str, params: List[tuple]) -> None:
        """执行批量SQL语句"""
        cursor = self.conn.cursor()
        cursor.executemany(query, params)
        self.conn.commit()

    def fetch_one(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """获取单条查询结果"""
        cursor = self.conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        result = cursor.fetchone()
        return dict(result) if result else None

    def fetch_all(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """获取所有查询结果"""
        cursor = self.conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        results = cursor.fetchall()
        return [dict(row) for row in results]

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None