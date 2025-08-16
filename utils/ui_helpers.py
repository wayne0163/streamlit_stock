import os
import sys
from datetime import datetime, date
from typing import Set, Dict, Any

import streamlit as st
import pandas as pd

# Ensure project root on sys.path for pages
def ensure_project_path():
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def init_state():
    """Initialize shared objects in session state (idempotent)."""
    ensure_project_path()
    from data.database import Database
    from portfolio.manager import PortfolioManager
    from strategies.manager import StrategyManager
    from risk.analyzer import RiskAnalyzer
    from data.data_fetcher import DataFetcher

    if 'initialized' not in st.session_state:
        db = Database()
        st.session_state.db = db
        st.session_state.pm = PortfolioManager(db)
        st.session_state.sm = StrategyManager(db)
        st.session_state.ra = RiskAnalyzer(st.session_state.pm)
        st.session_state.df = DataFetcher(db)
        st.session_state.backtest_pool = load_backtest_pool_from_db(db)
        st.session_state.initialized = True
        st.session_state.message = None


def load_backtest_pool_from_db(db) -> Set[str]:
    pool_data = db.fetch_all("SELECT ts_code FROM watchlist WHERE in_pool = 1")
    return {item['ts_code'] for item in pool_data}


def show_status_panel():
    st.sidebar.divider()
    st.sidebar.subheader("系统状态")
    if 'message' in st.session_state and st.session_state.message:
        msg = st.session_state.message
        msg_type = msg.get('type', 'info')
        if msg_type == "success":
            st.sidebar.success(msg.get('body', '操作成功。'))
        elif msg_type == "error":
            st.sidebar.error(msg.get('body', '操作失败。'))
        else:
            st.sidebar.info(msg.get('body', '系统消息。'))
    else:
        st.sidebar.info("系统准备就绪，请选择操作。")


def render_watchlist_editor(db, item_type='stock'):
    """Extracted from legacy app for reuse in multipage."""
    watchlist_table = "watchlist" if item_type == 'stock' else "index_watchlist"
    master_table = "stocks" if item_type == 'stock' else "indices"
    type_name = "股票" if item_type == 'stock' else "指数"

    st.subheader(f"手动添加自选{type_name}")
    code_input_key = f"manual_{item_type}_input"
    code_input = st.text_input("输入6位股票代码" if item_type == 'stock' else "输入完整指数代码 (如 000300.SH)", key=code_input_key, max_chars=6 if item_type == 'stock' else None)
    if st.button(f"添加{type_name}", key=f"add_{item_type}"):
        if code_input:
            info = None
            if item_type == 'stock':
                info = db.fetch_one(f"SELECT ts_code, name FROM {master_table} WHERE symbol = ?", (code_input,))
            else:
                info = db.fetch_one(f"SELECT ts_code, name FROM {master_table} WHERE ts_code = ?", (code_input,))
            if info and info.get('name') and info.get('ts_code'):
                db.execute(f"INSERT OR IGNORE INTO {watchlist_table} (ts_code, name, add_date, in_pool) VALUES (?, ?, ?, ?)",
                           (info['ts_code'], info['name'], datetime.now().strftime('%Y-%m-%d'), 0))
                st.session_state.message = {"type": "success", "body": f"已将 {info['name']} ({info['ts_code']}) 添加到您的自选列表。"}
            else:
                st.session_state.message = {"type": "error", "body": f"本地基础信息中未找到代码 {code_input}。请先在“数据管理”页面更新全市场{type_name}列表。"}
            st.rerun()

    st.divider()
    st.subheader(f"通过CSV批量导入自选{type_name}")
    upload_key = f"upload_{item_type}"
    if item_type == 'stock':
        help_text = "上传包含 'symbol' 列 (6位股票代码) 的CSV文件"
        col_name = 'symbol'
    else:
        help_text = "上传包含 'ts_code' 列 (完整指数代码) 的CSV文件"
        col_name = 'ts_code'
    uploaded_file = st.file_uploader(help_text, type="csv", key=upload_key)
    if uploaded_file:
        try:
            df_upload = pd.read_csv(uploaded_file, dtype=str, engine='python')
            if col_name not in df_upload.columns:
                st.error(f"上传的CSV文件必须包含一个名为 '{col_name}' 的列。")
            else:
                codes_to_process = df_upload[col_name].dropna().unique().tolist()
                success_count = 0
                with st.spinner(f"正在从本地数据库匹配信息并导入..."):
                    for code in codes_to_process:
                        info = None
                        if item_type == 'stock':
                            info = db.fetch_one(f"SELECT ts_code, name FROM {master_table} WHERE symbol = ?", (code,))
                        else:
                            info = db.fetch_one(f"SELECT ts_code, name FROM {master_table} WHERE ts_code = ?", (code,))
                        if info and info.get('name') and info.get('ts_code'):
                            db.execute(f"INSERT OR IGNORE INTO {watchlist_table} (ts_code, name, add_date, in_pool) VALUES (?, ?, ?, ?)",
                                       (info['ts_code'], info['name'], datetime.now().strftime('%Y-%m-%d'), 0))
                            success_count += 1
                st.session_state.message = {"type": "success", "body": f"批量操作完成，成功从本地数据库匹配并导入 {success_count}/{len(codes_to_process)} 个条目。"}
                st.rerun()
        except Exception as e:
            st.error(f"处理CSV文件时出错: {e}")

    st.divider()
    st.subheader(f"当前自选{type_name}列表")
    watchlist = db.fetch_all(f"SELECT ts_code, name, in_pool FROM {watchlist_table} ORDER BY ts_code")
    if watchlist:
        df_watch = pd.DataFrame(watchlist)
        df_watch['delete'] = False
        df_watch['in_pool'] = df_watch['in_pool'].astype(bool)

        if item_type == 'stock':
            column_config = {
                "ts_code": st.column_config.TextColumn("代码", disabled=True),
                "name": st.column_config.TextColumn("名称", disabled=True),
                "in_pool": st.column_config.CheckboxColumn("加入回测池"),
                "delete": st.column_config.CheckboxColumn("删除")
            }
            display_columns = ['ts_code', 'name', 'in_pool', 'delete']
        else:
            column_config = {
                "ts_code": st.column_config.TextColumn("代码", disabled=True),
                "name": st.column_config.TextColumn("名称", disabled=True),
                "delete": st.column_config.CheckboxColumn("删除")
            }
            display_columns = ['ts_code', 'name', 'delete']

        edited_df = st.data_editor(df_watch, column_config=column_config, hide_index=True, key=f"editor_{item_type}", column_order=display_columns)
        st.write("**批量操作**")
        cols = st.columns(5 if item_type == 'stock' else 3)
        if item_type == 'stock':
            if cols[0].button("全选加入回测池", key=f"pool_add_all_{item_type}"):
                db.execute("UPDATE watchlist SET in_pool = 1")
                st.session_state.backtest_pool = load_backtest_pool_from_db(db)
                st.rerun()
            if cols[1].button("全部移出回测池", key=f"pool_remove_all_{item_type}"):
                db.execute("UPDATE watchlist SET in_pool = 0")
                st.session_state.backtest_pool.clear()
                st.rerun()
            if cols[2].button("更新回测池选择", key=f"update_pool_{item_type}"):
                db.execute("UPDATE watchlist SET in_pool = 0")
                codes_to_add = edited_df[edited_df["in_pool"]]["ts_code"].tolist()
                if codes_to_add:
                    placeholders = ','.join('?' for _ in codes_to_add)
                    db.execute(f"UPDATE watchlist SET in_pool = 1 WHERE ts_code IN ({placeholders})", tuple(codes_to_add))
                st.session_state.backtest_pool = set(codes_to_add)
                st.session_state.message = {"type": "info", "body": "回测池已根据您的勾选更新。"}
                st.rerun()

        delete_button_col = cols[3] if item_type == 'stock' else cols[0]
        clear_button_col = cols[4] if item_type == 'stock' else cols[1]

        if delete_button_col.button("删除选中项", key=f"delete_items_{item_type}"):
            codes_to_delete = edited_df[edited_df["delete"]]["ts_code"].tolist()
            if codes_to_delete:
                placeholders = ','.join('?' for _ in codes_to_delete)
                db.execute(f"DELETE FROM {watchlist_table} WHERE ts_code IN ({placeholders})", tuple(codes_to_delete))
                if item_type == 'stock':
                    st.session_state.backtest_pool.difference_update(codes_to_delete)
                st.session_state.message = {"type": "success", "body": f"成功删除 {len(codes_to_delete)} 个条目。"}
                st.rerun()
            else:
                st.warning("没有勾选要删除的项目。")

        if clear_button_col.button(f"清空所有{type_name}", key=f"clear_all_{item_type}", type="primary"):
            db.execute(f"DELETE FROM {watchlist_table}")
            if item_type == 'stock':
                st.session_state.backtest_pool.clear()
            st.session_state.message = {"type": "success", "body": f"已清空所有自选{type_name}。"}
            st.rerun()
    else:
        st.info(f"您的自选{type_name}列表为空。")

