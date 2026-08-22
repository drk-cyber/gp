# -*- coding: utf-8 -*-
"""
SQLite 本地缓存：首次拉取后缓存，后续直接读取，支持增量更新
"""
import os
import sqlite3
import pandas as pd

import config

DB_PATH = os.path.join(config.DATA_DIR, "stock_data.db")


def _conn():
    os.makedirs(config.DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    return conn


def _init_table(conn, table):
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {table} (
            date TEXT,
            code TEXT,
            open REAL, high REAL, low REAL, close REAL,
            volume REAL, amount REAL,
            pct_chg REAL, turnover REAL,
            PRIMARY KEY (date, code)
        )
    """)
    conn.commit()


def _table_name(code):
    # 每个股票一张表，避免单表过大
    return "stock_" + code


def save_daily(code, df):
    """保存日线数据到缓存（增量合并）"""
    if df is None or df.empty:
        return
    table = _table_name(code)
    conn = _conn()
    _init_table(conn, table)
    rows = []
    for _, r in df.iterrows():
        rows.append((
            str(r.get("date")), code,
            float(r.get("open", 0)), float(r.get("high", 0)),
            float(r.get("low", 0)), float(r.get("close", 0)),
            float(r.get("volume", 0)), float(r.get("amount", 0)),
            float(r.get("pct_chg", 0)) if pd.notna(r.get("pct_chg", 0)) else 0,
            float(r.get("turnover", 0)) if pd.notna(r.get("turnover", 0)) else 0,
        ))
    conn.executemany(f"""
        INSERT OR REPLACE INTO {table}
        (date, code, open, high, low, close, volume, amount, pct_chg, turnover)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()
    conn.close()


def load_daily(code):
    """从缓存读取日线数据，返回 DataFrame（按日期升序）"""
    table = _table_name(code)
    conn = _conn()
    try:
        df = pd.read_sql_query(
            f"SELECT * FROM {table} ORDER BY date ASC", conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def latest_date(code):
    """获取某股票本地缓存的最新日期（用于增量更新）"""
    table = _table_name(code)
    conn = _conn()
    try:
        cur = conn.execute(f"SELECT MAX(date) FROM {table}")
        val = cur.fetchone()[0]
    except Exception:
        val = None
    conn.close()
    return val
