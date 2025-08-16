import os
import sys
from datetime import date
import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.ui_helpers import init_state, show_status_panel
from backtest.engine import run_backtest

init_state()
show_status_panel()

db = st.session_state.db
sm = st.session_state.sm

st.header("回测引擎")
st.subheader("回测参数设置")
col1, col2 = st.columns(2)
initial_capital = col1.number_input("初始资金", min_value=10000, value=1000000, step=10000, help="用于回测的起始现金总额。")
max_positions = col2.number_input("最大持仓股票数", min_value=1, value=5, step=1, help="允许同时持有的最大股票数量。")

strategy_name = st.selectbox("选择一个交易策略", list(sm.strategies.keys()))

# 策略参数（当前仅对 SMA20_120_VolStop30Strategy 暴露）
strategy_params = {}
if strategy_name == 'SMA20_120_VolStop30Strategy':
    st.subheader("策略参数设置（SMA20/120 + 量能过滤）")
    c1, c2, c3 = st.columns(3)
    sma_fast = c1.number_input("SMA 快线周期", min_value=5, max_value=120, value=20, step=1)
    sma_slow = c2.number_input("SMA 慢线周期", min_value=30, max_value=400, value=120, step=1)
    sma_stop = c3.number_input("止损均线周期", min_value=10, max_value=120, value=30, step=1)
    c4, c5 = st.columns(2)
    vol_ma_short = c4.number_input("量能MA短（天）", min_value=2, max_value=30, value=3, step=1)
    vol_ma_long = c5.number_input("量能MA长（天）", min_value=5, max_value=60, value=18, step=1)
    valid_days = st.number_input("信号有效天数（N日内有效）", min_value=1, max_value=20, value=3, step=1, help="金叉后N日内有效，需满足当日价≥快线且量能持续")
    strategy_params = {
        'sma_fast': int(sma_fast),
        'sma_slow': int(sma_slow),
        'sma_stop': int(sma_stop),
        'vol_ma_short': int(vol_ma_short),
        'vol_ma_long': int(vol_ma_long),
        'signal_valid_days': int(valid_days),
    }
elif strategy_name == 'WeeklyMACDFilterStrategy':
    st.subheader("策略参数设置（周线MACD + 日线过滤）")
    valid_days = st.number_input("周线信号有效天数（N日内有效）", min_value=1, max_value=20, value=3, step=1,
                              help="周线信号出现后N个交易日内有效，需当日满足价>20日线且量>MA3与MA18")
    strategy_params = {
        'signal_valid_days': int(valid_days)
    }
date_range = st.date_input("选择回测时间周期", [date(2024, 1, 1), date.today()], key="backtest_date_range")
normalized = st.toggle("显示归一化净值（与沪深300对比）", value=True)
if date_range and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = date(2024, 1, 1), date.today()
    st.warning("日期范围选择不完整，已自动重置为默认值。")

st.divider()
st.subheader("执行回测")
backtest_pool = st.session_state.get('backtest_pool', set())
if not backtest_pool:
    st.warning("您的回测池为空。请先在“自选列表管理”页面将股票加入回测池。")
else:
    st.success(f"当前回测池中有 {len(backtest_pool)} 只股票可供回测。")
    st.info("提示：回测会自动忽略样本长度不足 241 个交易日的股票。")
    with st.expander("查看回测池中的股票"):
        placeholders = ','.join('?' for _ in backtest_pool)
        query = f"SELECT ts_code, name FROM watchlist WHERE ts_code IN ({placeholders})"
        pool_details = db.fetch_all(query, tuple(backtest_pool))
        if pool_details:
            import pandas as pd
            st.dataframe(pd.DataFrame(pool_details), hide_index=True)

    if st.button("开始回测", type="primary"):
        start_str, end_str = start_date.strftime('%Y%m%d'), end_date.strftime('%Y%m%d')
        with st.spinner(f"正在使用 Backtrader 引擎进行回测..."):
            result = run_backtest(strategy_name, list(backtest_pool), start_str, end_str, initial_capital, max_positions, normalized, strategy_params)
            if result:
                st.subheader("回测结果摘要")
                metrics = result.get('metrics', {})
                cols = st.columns(4)
                cols[0].metric("策略总收益率", f"{metrics.get('total_return', 0):.2f}%")
                cols[1].metric("策略年化收益率", f"{metrics.get('annual_return', 0):.2f}%")
                cols[2].metric("最大回撤", f"{metrics.get('max_drawdown', 0):.2f}%")
                cols[3].metric("夏普比率", f"{metrics.get('sharpe_ratio') or 0:.2f}")
                st.subheader("回测图表")
                st.plotly_chart(result['plot_figure'], use_container_width=True)

                # 展示被忽略的股票（样本不足）
                skipped = result.get('skipped_ts_codes') or []
                if skipped:
                    st.info(f"有 {len(skipped)} 只股票因样本长度不足（< {result.get('min_required_bars', 241)} 个交易日）被忽略。")
                    try:
                        placeholders = ','.join('?' for _ in skipped)
                        q = f"SELECT ts_code, name FROM watchlist WHERE ts_code IN ({placeholders})"
                        rows = db.fetch_all(q, tuple(skipped))
                        if rows:
                            import pandas as pd
                            with st.expander("查看被忽略的股票名单"):
                                st.dataframe(pd.DataFrame(rows), hide_index=True)
                        else:
                            st.write(', '.join(skipped))
                    except Exception:
                        st.write(', '.join(skipped))
                if result.get('trades_csv'):
                    try:
                        with open(result['trades_csv'], 'rb') as f:
                            st.download_button(
                                label="下载回测交易记录",
                                data=f.read(),
                                file_name=os.path.basename(result['trades_csv']),
                                mime="text/csv"
                            )
                    except Exception:
                        st.info("交易记录文件暂不可用。")
                if result.get('orders_csv'):
                    try:
                        with open(result['orders_csv'], 'rb') as f:
                            st.download_button(
                                label="下载订单执行明细（含买入/卖出）",
                                data=f.read(),
                                file_name=os.path.basename(result['orders_csv']),
                                mime="text/csv"
                            )
                    except Exception:
                        st.info("订单执行明细文件暂不可用。")
            else:
                st.error("回测执行失败或没有产生任何结果。")
