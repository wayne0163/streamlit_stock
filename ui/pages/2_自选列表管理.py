import os
import sys
import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.ui_helpers import init_state, show_status_panel, render_watchlist_editor

init_state()
show_status_panel()

db = st.session_state.db

st.header("自选列表管理")
stock_tab, index_tab = st.tabs(["自选股", "自选指数"])
with stock_tab:
    render_watchlist_editor(db, 'stock')
with index_tab:
    render_watchlist_editor(db, 'index')

