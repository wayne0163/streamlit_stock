import os
import sys
import streamlit as st
import pandas as pd
import plotly.express as px

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.ui_helpers import init_state, show_status_panel

init_state()
show_status_panel()

ra = st.session_state.ra
pm = st.session_state.pm

st.header("风险分析")
if st.button("开始分析"):
    with st.spinner("正在进行风险分析..."):
        try:
            risk_report = ra.analyze_portfolio_risk()
            st.success("风险分析完成")
            st.subheader("风险指标")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("95% VaR", f"{risk_report['var_95']:.2f}%")
            col2.metric("99% VaR", f"{risk_report['var_99']:.2f}%")
            col3.metric("95% CVaR", f"{risk_report['cvar_95']:.2f}%")
            col4.metric("行业集中度 (HHI)", f"{risk_report['hhi']:.2f}")
            st.subheader("风险违规")
            if risk_report['violations']:
                st.dataframe(pd.DataFrame(risk_report['violations']))
            else:
                st.info("没有风险违规")
        except Exception as e:
            st.error(f"风险分析失败: {e}")

