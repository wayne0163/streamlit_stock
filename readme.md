streamlit-股票分析系统（精简版说明）

概览
- 模块：数据管理、标的池、策略选股、Backtrader 回测、风险分析、指数对比（Streamlit 界面）
- 存储：SQLite（自动建表、建索引、WAL 优化）
- 数据：Tushare（请配置环境变量 `TUSHARE_TOKEN` 或在运行环境设置相同变量）

新增策略
- `WeeklyMACDFilterStrategy`：周线 MACD（金叉 + DIF 范围 + 20 周 20% 分位）趋势确认；配合日线量价过滤（量 > MA3 与 MA18、收盘价 > SMA20）；当日收盘买入，跌破 SMA20 次日开盘卖出。
- `SMA20_120_VolStop30Strategy`：20日均线与120日均线金叉，且当日成交量 > MA3 与 > MA18 则买入（当日收盘）；当收盘价跌破30日均线时，次日开盘卖出。

快速开始
- 安装依赖：`pip install -r requirements.txt`
- 设置 Token：`export TUSHARE_TOKEN=你的token`
- 运行：`streamlit run ui/app.py`

选股/回测使用
- 选股：在“选股策略”页面选择 `WeeklyMACDFilterStrategy`，点击开始选股。
- 回测：在“回测引擎”页面选择 `WeeklyMACDFilterStrategy`，设置时间区间、初始资金与最大持仓后执行。
- 同理，可选择 `SMA20_120_VolStop30Strategy` 进行选股与回测。

可调参数
- `SMA20_120_VolStop30Strategy`：
  - 快/慢/止损均线周期（默认 20/120/30）
  - 量能MA短/长（默认 3/18）
  - 信号有效天数 N（默认 3）：金叉发生后 N 日内仍可触发买入，但需在“判定日”满足价≥快线、量≥MA3与MA18。
- `WeeklyMACDFilterStrategy`：
  - 信号有效天数 N（默认 3）：周线信号（周五收盘确认）发生后 N 个交易日内有效，且判定日需满足价>20日线与量>MA3、MA18。

离线示例（可选）
- 生成示例选股 CSV：`python scripts/generate_macd_weekly_filter_sample.py`
  - 输出文件位于 `output/screening_WeeklyMACDFilterStrategy_sample.csv`

已做的优化
- 数据库：WAL + 索引（daily_price/index_daily_price/watchlist）提升读写性能
- 日志：核心路径改为标准 logging（便于调试与追踪）
- 选股：对 FiveStep 策略新增 `screen_stock(df)`，精确按“最后一日”判定信号
- 选股：新增 `WeeklyMACDFilterStrategy`，提供与回测一致的 `screen_stock(df)` 逻辑
- 回测：导出交易记录 CSV，并在 UI 中提供下载按钮

后续建议（可选）
- UI 拆分为多页（`pages/`）并统一消息提示组件
- 组合净值快照与更准确的风险指标（基于每日持仓估值）
- 增加测试与 CI、代码静态检查
