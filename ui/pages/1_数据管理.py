import os
import sys
from datetime import date
import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.ui_helpers import init_state, show_status_panel

init_state()
show_status_panel()

db = st.session_state.db
data_fetcher = st.session_state.df

st.header("数据管理")
st.subheader("基础信息更新")
st.info("首次使用或需要更新市场股票/指数列表时，请点击下方按钮。")
c1, c2 = st.columns(2)
if c1.button("更新全市场股票列表"):
    with st.spinner("正在更新全市场股票基础信息..."):
        count = data_fetcher.update_all_stock_basics()
        st.session_state.message = {"type": "success", "body": f"全市场股票列表更新完成，共处理 {count} 只股票。"}
        st.rerun()
if c2.button("更新全市场指数列表"):
    with st.spinner("正在更新全市场指数基础信息..."):
        count = data_fetcher.update_all_index_basics()
        st.session_state.message = {"type": "success", "body": f"全市场指数列表更新完成，共处理 {count} 个指数。"}
        st.rerun()

st.divider()
st.subheader("行情数据更新")
st.info("根据您在“自选列表管理”中添加的股票和指数，更新它们的日线行情数据。")

force_update = st.checkbox("强制刷新所有数据", value=False, key="force_update_checkbox")
help_text = "选中此项将删除所选列表的全部现有数据，并从下方指定的起始日期开始重新全量下载。"
start_date_input = st.date_input("数据起始日期", value=date(2024, 1, 1), help=help_text, disabled=not force_update)

c3, c4 = st.columns(2)
if c3.button("更新自选股行情数据"):
    start_date_str = start_date_input.strftime('%Y%m%d') if force_update else None
    with st.spinner("正在更新自选股数据..."):
        count = data_fetcher.update_watchlist_data(force_start_date=start_date_str)
        st.session_state.message = {"type": "success", "body": f"自选股数据更新完成，共处理 {count} 只股票。"}
        st.rerun()
if c4.button("更新自选指数行情数据"):
    start_date_str = start_date_input.strftime('%Y%m%d') if force_update else None
    with st.spinner("正在更新自选指数数据..."):
        count = data_fetcher.update_index_watchlist_data(force_start_date=start_date_str)
        st.session_state.message = {"type": "success", "body": f"自选指数数据更新完成，共处理 {count} 个指数。"}
        st.rerun()

