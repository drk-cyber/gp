# -*- coding: utf-8 -*-
"""
全局配置：交易成本、回测参数、路径等
"""
import os

# ---------- 项目路径 ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data_cache")      # SQLite 缓存目录
REPORT_DIR = os.path.join(BASE_DIR, "reports")       # 报告输出目录

# ---------- 交易成本（A股真实规则，可自行修改） ----------
COMMISSION_RATE = 0.00025      # 佣金：万 2.5
MIN_COMMISSION = 5.0           # 最低佣金 5 元
STAMP_TAX_RATE = 0.0005        # 印花税：卖出单边千 0.5
TRANSFER_FEE_RATE = 0.00001    # 过户费：双边万 0.1

# ---------- 回测默认参数 ----------
INITIAL_CASH = 100000.0        # 初始资金 10 万
SLIPPAGE = 0.0                 # 滑点比例（例如 0.001 表示 0.1%）
LOT_SIZE = 100                 # A股一手 100 股
RISK_FREE_RATE = 0.02          # 无风险利率（用于夏普比率），年化 2%

# ---------- 选股推荐默认参数 ----------
TOP_N = 10                     # 默认推荐股票数量
MIN_TURNOVER = 5000 * 10000    # 最低日均成交额过滤（5000 万）
LIQUIDITY_LIMIT = 5000 * 10000 # 流动性阈值
CANDIDATE_LIMIT = 50           # 初筛后进入深度技术面打分的股票上限
HISTORY_DAYS = 800             # 深度分析时拉取的历史天数（约3年）


def ensure_dirs():
    """确保必要目录存在"""
    for d in (DATA_DIR, REPORT_DIR):
        os.makedirs(d, exist_ok=True)
