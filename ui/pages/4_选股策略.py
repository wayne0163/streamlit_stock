import os
import sys
import streamlit as st
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.ui_helpers import init_state, show_status_panel

init_state()
show_status_panel()

db = st.session_state.db
sm = st.session_state.sm

st.header("选股策略")
strategy_name = st.selectbox("选择一个选股策略", list(sm.strategies.keys()))

# 策略可选参数（当前仅对 SMA20_120_VolStop30Strategy 暴露）
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
if st.button("开始选股", type="primary"):
    stocks = db.fetch_all("SELECT ts_code FROM watchlist")
    if not stocks:
        st.error("错误：您的自选股列表为空。请先在“自选列表管理”页面添加股票。")
        st.stop()

    stock_codes = [stock['ts_code'] for stock in stocks]
    with st.spinner(f"正在对自选股池中的 {len(stock_codes)} 只股票运行 ‘{strategy_name}’ 策略..."):
        results = st.session_state.sm.run_screening(strategy_name, stock_codes, strategy_params=strategy_params)
        if results:
            st.success(f"策略运行完成，共筛选出 {len(results)} 只符合条件的股票。")
            df_results = pd.DataFrame(results)
            st.dataframe(df_results)
            st.download_button(
                label="下载选股结果 CSV",
                data=df_results.to_csv(index=False).encode('utf-8-sig'),
                file_name=f"screening_{strategy_name}.csv",
                mime="text/csv"
            )
        else:
            st.info("根据最新数据，您的自选股中没有找到符合该策略条件的股票。")
