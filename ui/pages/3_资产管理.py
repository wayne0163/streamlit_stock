import os
import sys
import streamlit as st
import pandas as pd
import plotly.express as px

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.ui_helpers import init_state, show_status_panel
from utils.code_processor import to_ts_code

init_state()
show_status_panel()

pm = st.session_state.pm
db = st.session_state.db

st.header("资产管理")
if not pm.is_initialized():
    st.subheader("设置初始模拟资金")
    initial_cash = st.number_input("输入您的初始现金总额", min_value=0.0, value=1000000.0, format="%.2f")
    if st.button("开始交易"):
        pm.initialize_cash(initial_cash)
        st.session_state.message = {"type": "success", "body": f"资金初始化成功，当前现金: {initial_cash:.2f}"}
        st.rerun()
else:
    st.subheader("手动交易")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        manual_code_input = st.text_input("输入6位股票代码", max_chars=6)
    with col2:
        trade_type = st.radio("交易类型", ["买入", "卖出"])
    with col3:
        price = st.number_input("价格", min_value=0.0, format="%.2f", value=None, placeholder="请输入价格")
    with col4:
        qty = st.number_input("数量", min_value=0, format="%d", value=None, placeholder="请输入数量")

    if st.button("执行交易"):
        if not all([manual_code_input, price, qty]):
            st.warning("股票代码、价格和数量均为必填项。")
        else:
            ts_code_to_trade = to_ts_code(manual_code_input)
            side = "buy" if trade_type == "买入" else "sell"
            try:
                pm.add_trade(side=side, ts_code=ts_code_to_trade, price=price, qty=qty)
                st.session_state.message = {"type": "success", "body": f"交易执行成功: {trade_type} {qty} 股 {ts_code_to_trade}"}
                st.rerun()
            except ValueError as e:
                st.session_state.message = {"type": "error", "body": f"交易失败: {e}"}
                st.rerun()

    st.divider()
    st.subheader("投资组合概览")
    if st.button("刷新投资组合报告"):
        with st.spinner("正在生成投资组合报告..."):
            report = pm.generate_portfolio_report()
            st.metric("总资产", f"¥{report['summary']['total_value']:.2f}")
            col1, col2, col3 = st.columns(3)
            col1.metric("现金", f"¥{report['cash']:.2f}")
            col2.metric("持仓市值", f"¥{report['summary']['investment_value']:.2f}")
            col3.metric("持仓数量", report['summary']['position_count'])
            if report['positions']:
                df_pos = pd.DataFrame(report['positions'])
                df_pos.rename(columns={'ts_code': '股票代码', 'name': '股票名称', 'qty': '持仓数量', 'cost_price': '成本价', 'current_price': '现价', 'market_value': '市值', 'pnl': '浮动盈亏'}, inplace=True)
                st.dataframe(df_pos)
                fig = px.pie(df_pos, values='市值', names='股票名称', title='持仓分布')
                st.plotly_chart(fig)
            else:
                st.info("当前无任何持仓")

    st.divider()
    st.subheader("净值快照")
    c1, c2 = st.columns(2)
    if c1.button("重建净值快照"):
        with st.spinner("正在重建净值快照..."):
            days = pm.rebuild_snapshots()
            st.success(f"已生成 {days} 天的组合净值快照。")
    if c2.button("查看净值曲线"):
        df_snap = pm.get_snapshots()
        if df_snap is not None and not df_snap.empty:
            import plotly.express as px
            fig = px.line(df_snap.reset_index(), x='date', y='total_value', title='组合净值曲线')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("暂无快照数据，请先重建净值快照。")
