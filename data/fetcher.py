# -*- coding: utf-8 -*-
"""
数据获取模块：基于 AkShare 获取 A股行情数据
- 个股日线（前复权）
- 全部 A股实时行情（用于选股扫描）
- 指数日线（用于大盘状态判断）
"""
import time
import pandas as pd

import config
from data import cache


def _safe_import_akshare():
    try:
        import akshare as ak
        return ak
    except ImportError:
        raise RuntimeError(
            "未安装 akshare，请先运行： pip install akshare\n"
            "（数据源依赖网络，请确保能访问互联网）"
        )


def _to_sina_symbol(code):
    """6位代码 -> 新浪带市场前缀代码"""
    code = str(code).zfill(6)
    if code.startswith(("60", "68", "90")):
        return "sh" + code
    if code.startswith(("00", "30", "20")):
        return "sz" + code
    if code.startswith(("8", "4")):
        return "bj" + code
    return "sh" + code


def _fetch_sina(code, start_dt, end_dt, adjust):
    """
    新浪数据源（备用）：ak.stock_zh_a_daily
    返回统一格式 DataFrame
    """
    ak = _safe_import_akshare()
    symbol = _to_sina_symbol(code)
    df = ak.stock_zh_a_daily(
        symbol=symbol,
        start_date=start_dt.strftime("%Y%m%d"),
        end_date=end_dt.strftime("%Y%m%d"),
        adjust=adjust,
    )
    if df is None or df.empty:
        return df
    # 新浪源列名已是英文，统一为标准列
    col_map = {
        "date": "date", "open": "open", "high": "high", "low": "low",
        "close": "close", "volume": "volume", "amount": "amount",
        "turnover": "turnover",
    }
    df = df.rename(columns=col_map)
    df["date"] = pd.to_datetime(df["date"])
    if "pct_chg" not in df.columns:
        df["pct_chg"] = df["close"].pct_change().fillna(0) * 100
    keep = ["date", "open", "high", "low", "close", "volume", "amount",
            "pct_chg", "turnover"]
    for c in keep:
        if c not in df.columns:
            df[c] = 0.0
    return df[keep].sort_values("date").reset_index(drop=True)


def get_stock_daily(code, start_date=None, end_date=None, adjust="qfq",
                    use_cache=True, refresh=False):
    """
    获取个股日线数据（前复权），带本地缓存与增量更新
    :param code: 6 位股票代码，如 '600519'
    :param start_date: 'YYYY-MM-DD' 或 'YYYYMMDD'
    :param end_date: 同 start_date
    :param adjust: 'qfq' 前复权 / 'hfq' 后复权 / '' 不复权
    :return: DataFrame，列：date, open, high, low, close, volume, amount, pct_chg, turnover
    """
    code = str(code).zfill(6)

    # 先看缓存
    cached = cache.load_daily(code) if use_cache else pd.DataFrame()

    # 目标日期范围（datetime）
    if start_date:
        start_dt = pd.to_datetime(str(start_date).replace("-", ""))
    else:
        start_dt = cached["date"].min() if not cached.empty else pd.to_datetime("20050101")
    if end_date:
        end_dt = pd.to_datetime(str(end_date).replace("-", ""))
    else:
        end_dt = pd.Timestamp.today()

    # 若缓存已完整覆盖目标区间，直接返回缓存切片
    if use_cache and not refresh and not cached.empty:
        cache_min = cached["date"].min()
        cache_max = cached["date"].max()
        if cache_min <= start_dt and cache_max >= end_dt:
            mask = (cached["date"] >= start_dt) & (cached["date"] <= end_dt)
            return cached[mask].reset_index(drop=True)

    # 需要拉取 [start_dt, end_dt]，再与缓存合并
    fetch_start = start_dt.strftime("%Y%m%d")
    fetch_end = end_dt.strftime("%Y%m%d")

    df = None
    last_err = None
    # 主源：东方财富
    try:
        ak = _safe_import_akshare()
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=fetch_start,
            end_date=fetch_end,
            adjust=adjust,
        )
    except Exception as e:
        last_err = e

    # 备用源：新浪（东方财富失败时自动切换）
    if df is None or df.empty:
        try:
            df = _fetch_sina(code, start_dt, end_dt, adjust)
        except Exception as e:
            last_err = e

    if df is None or df.empty:
        if not cached.empty:
            print(f"  [警告] 拉取 {code} 失败，使用本地缓存：{last_err}")
            mask = (cached["date"] >= start_dt) & (cached["date"] <= end_dt)
            return cached[mask].reset_index(drop=True)
        raise RuntimeError(f"获取 {code} 数据失败：{last_err}")

    # 统一列名
    col_map = {
        "日期": "date", "开盘": "open", "收盘": "close", "最高": "high",
        "最低": "low", "成交量": "volume", "成交额": "amount",
        "涨跌幅": "pct_chg", "换手率": "turnover",
    }
    df = df.rename(columns=col_map)
    df["date"] = pd.to_datetime(df["date"])
    keep = ["date", "open", "high", "low", "close", "volume", "amount",
            "pct_chg", "turnover"]
    df = df[[c for c in keep if c in df.columns]]
    for c in keep:
        if c not in df.columns:
            df[c] = 0.0
    df = df.sort_values("date").reset_index(drop=True)

    # 与缓存合并去重
    if not cached.empty:
        merged = pd.concat([cached, df]).drop_duplicates(
            subset=["date"], keep="last").sort_values("date").reset_index(drop=True)
    else:
        merged = df

    # 写入缓存
    if use_cache:
        try:
            cache.save_daily(code, merged)
        except Exception:
            pass

    # 返回目标区间切片
    mask = (merged["date"] >= start_dt) & (merged["date"] <= end_dt)
    return merged[mask].reset_index(drop=True)


def get_all_spot():
    """
    获取全部 A股实时行情快照（用于选股扫描）
    :return: DataFrame，列：code, name, price, pct_chg, turnover, volume,
             amount, pe, pb, total_mv, circ_mv, ...
    数据源依次尝试：东方财富 → 腾讯 → 新浪
    """
    ak = _safe_import_akshare()
    df = None

    # 源1：东方财富（字段最全）
    if df is None or df.empty:
        try:
            df = ak.stock_zh_a_spot_em()
            df = df.rename(columns={
                "代码": "code", "名称": "name", "最新价": "price", "涨跌幅": "pct_chg",
                "成交量": "volume", "成交额": "amount", "换手率": "turnover",
                "市盈率-动态": "pe", "市净率": "pb",
                "总市值": "total_mv", "流通市值": "circ_mv",
                "今开": "open", "最高": "high", "最低": "low", "昨收": "pre_close",
            })
        except Exception:
            df = None

    # 源2：腾讯（字段较全，含 5/10/20/60 日涨跌幅）
    if df is None or df.empty:
        try:
            df = ak.stock_zh_a_spot_tx()
            df = df.rename(columns={
                "zxj": "price", "zdf": "pct_chg", "pe_ttm": "pe",
                "zsz": "total_mv", "ltsz": "circ_mv",
                "zdf_d60": "60日涨跌幅",
            })
            # 成交额（原 turnover，单位万元）→ amount（元）；换手率（原 hsl）→ turnover
            df = df.rename(columns={"turnover": "amount", "hsl": "turnover"})
            df["amount"] = pd.to_numeric(df["amount"], errors="coerce") * 1e4
            for c in ("total_mv", "circ_mv"):
                df[c] = pd.to_numeric(df[c], errors="coerce") * 1e8
        except Exception:
            df = None

    # 源3：新浪（字段较少，缺 PE/PB/换手率）
    if df is None or df.empty:
        try:
            df = ak.stock_zh_a_spot()
            df = df.rename(columns={
                "代码": "code", "名称": "name", "最新价": "price", "涨跌幅": "pct_chg",
                "成交量": "volume", "成交额": "amount", "今开": "open",
                "最高": "high", "最低": "low", "昨收": "pre_close",
            })
        except Exception as e:
            raise RuntimeError(f"获取全市场行情失败（东财/腾讯/新浪均不可用）：{e}")

    df["code"] = df["code"].astype(str).str.replace(
        r"[^0-9]", "", regex=True).str[-6:].str.zfill(6)
    # 补齐缺失的字段列
    for c in ["price", "pct_chg", "turnover", "volume", "amount",
              "pe", "pb", "total_mv", "circ_mv", "open", "high", "low", "pre_close",
              "60日涨跌幅"]:
        if c not in df.columns:
            df[c] = None
        else:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def get_index_daily(symbol="sh000001", start_date="20150101", end_date=None):
    """
    获取指数日线（用于大盘趋势判断）
    :param symbol: 'sh000001'(上证) / 'sz399001'(深成) / 'sz399006'(创业板)
    """
    ak = _safe_import_akshare()
    if end_date is None:
        end_date = pd.Timestamp.today().strftime("%Y%m%d")
    try:
        df = ak.stock_zh_index_daily(symbol=symbol)
    except Exception:
        df = ak.stock_zh_index_daily_em(symbol=symbol)
    df = df.rename(columns={"date": "date", "open": "open", "high": "high",
                            "low": "low", "close": "close", "volume": "volume"})
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["date"] >= pd.to_datetime(start_date[:4] + "-" + start_date[4:6] + "-" + start_date[6:])]
    df = df.sort_values("date").reset_index(drop=True)
    return df


def get_stock_name(code):
    """根据代码查股票名称（从全市场快照中）"""
    try:
        spot = get_all_spot()
        row = spot[spot["code"] == str(code).zfill(6)]
        if not row.empty:
            return row.iloc[0]["name"]
    except Exception:
        pass
    return str(code)
