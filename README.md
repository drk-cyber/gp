# A股本地股票回测系统

一套可在本地运行的 A股股票回测 + 智能选股推荐系统，零代码门槛。

## 功能

- **股票回测**：内置双均线、MACD、RSI、布林带、KDJ、量价配合等策略
- **A股真实交易规则模拟**：T+1、涨跌停、佣金/印花税/过户费
- **绩效指标**：年化收益率、最大回撤、夏普比率、胜率、盈亏比等
- **智能选股推荐**：根据当前行情扫描全市场，多维度打分，输出推荐股票
- **HTML 可视化报告**：收益曲线、回撤曲线、交易明细，浏览器直接查看

## 安装

```bash
# 1. 安装依赖（需联网）
pip install -r requirements.txt
```

依赖：`akshare`（数据源）、`pandas`、`numpy`。

## 使用

### Web 界面（推荐）

```bash
# 启动服务
python webapp.py
```

浏览器打开 **http://127.0.0.1:8000**，即可在网页上完成选股推荐、策略回测、查看报告。

### 命令行模式

```bash
python main.py
```

### 选股推荐（核心功能）

```bash
# 默认推荐 10 只，风格自动判断
python main.py --recommend

# 指定数量和风格
python main.py --recommend --top 5 --style defensive

# 超跌反弹模式：找"趋势向上 + 近期超跌"的股票，含止盈止损位
python main.py --recommend --mode dip --top 10

# 超跌反弹·半年线版：趋势判断改用 120 日均线（半年线）
python main.py --recommend --mode dip120 --top 10
```

### 单策略回测

```bash
# 双均线策略回测贵州茅台
python main.py --strategy ma_cross --stock 600519 --start 2015-01-01 --end 2025-01-01
```

### 查看内置策略

```bash
python main.py --list
```

## 内置策略

| 策略名 | 说明 |
|--------|------|
| `ma_cross` | 双均线：短均线上穿长均线买入，下穿卖出 |
| `macd` | MACD金叉买入，死叉卖出 |
| `rsi` | RSI超卖回升买入，超买回落卖出 |
| `bollinger` | 布林带下轨反弹买入，上轨回落卖出 |
| `kdj` | KDJ低位金叉买入，死叉卖出 |
| `volume_price` | 放量突破20日高点买入，跌破20日低点卖出 |
| `grid` | 网格：均线中枢跌一格买入，涨一格卖出 |
| `dca` | 定投：每22个交易日投固定金额，长期持有 |
| `turtle` | 海龟：突破20日高点买入，跌破10日低点卖出 |

## 目录结构

```
gp2/
├── main.py             # 命令行入口
├── webapp.py           # Web 版入口（Flask）
├── templates/          # 前端页面
│   └── index.html
├── static/             # 前端静态资源
│   ├── style.css
│   └── app.js
├── config.py           # 配置（交易成本等）
├── data/               # 数据获取 + SQLite 缓存
├── engine/             # 回测引擎 + 绩效指标
├── strategies/         # 策略库
├── screener/           # 选股推荐（行情判断/过滤/打分/信号）
├── report/             # HTML 报告生成
├── utils/              # 技术指标计算
├── data_cache/         # 本地数据缓存（自动生成）
└── reports/            # 报告输出目录（自动生成）
```

## 说明

- 首次运行会拉取历史数据并缓存到本地 `data_cache/`，之后增量更新。
- 选股推荐会扫描全市场，先粗筛再对候选做深度技术分析，需要一点时间，请耐心等待。
- 数据源依赖互联网，需能访问行情接口。

> 本工具仅供学习研究，回测/推荐结果不构成投资建议。股市有风险，入市需谨慎。
