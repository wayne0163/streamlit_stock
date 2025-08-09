import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import sys
import os

# --- Path Setup ---
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data.database import Database
from data.data_fetcher import DataFetcher
from portfolio.manager import PortfolioManager
from strategies.manager import StrategyManager
from backtest.engine import run_backtest
from risk.analyzer import RiskAnalyzer
from config.settings import get_settings
from utils.code_processor import to_ts_code
from analysis.market_comparison import compare_indices

# --- App Initialization ---
st.set_page_config(page_title="WaySsystem - 量化交易管理系统", page_icon="📈", layout="wide")

# --- Functions ---
def load_backtest_pool_from_db(db_conn):
    pool_data = db_conn.fetch_all("SELECT ts_code FROM watchlist WHERE in_pool = 1")
    return {item['ts_code'] for item in pool_data}

@st.cache_data
def get_guide_content():
    return """
# WaySsystem - 系统说明与操作指南

(详细指南内容省略...)
"""

def display_status():
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

# --- App Initialization ---
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

db = st.session_state.db
pm = st.session_state.pm
sm = st.session_state.sm
ra = st.session_state.ra
data_fetcher = st.session_state.df

def render_watchlist_editor(item_type='stock'):
    watchlist_table = "watchlist" if item_type == 'stock' else "index_watchlist"
    master_table = "stocks" if item_type == 'stock' else "indices"
    type_name = "股票" if item_type == 'stock' else "指数"

    st.subheader(f"手动添加自选{type_name}")
    code_input_key = f"manual_{item_type}_input"
    if item_type == 'stock':
        code_input = st.text_input("输入6位股票代码", key=code_input_key, max_chars=6)
    else:
        code_input = st.text_input("输入完整指数代码 (如 000300.SH)", key=code_input_key)

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
                st.session_state.message = {"type": "error", "body": f"本地基础信息中未找到代码 {code_input}。请先在‘数据管理’页面更新全市场{type_name}列表。"}
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
        if item_type == 'stock':
            df_watch['in_pool'] = df_watch['in_pool'].astype(bool)
            column_config = {
                "ts_code": st.column_config.TextColumn("代码", disabled=True),
                "name": st.column_config.TextColumn("名称", disabled=True),
                "in_pool": st.column_config.CheckboxColumn("加入回测池"), 
                "delete": st.column_config.CheckboxColumn("删除")
            }
            display_columns = ['ts_code', 'name', 'in_pool', 'delete']
        else:
            df_watch['in_pool'] = df_watch['in_pool'].astype(bool)
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
                st.warning("没有勾选要删除的项目。" )

        if clear_button_col.button(f"清空所有{type_name}", key=f"clear_all_{item_type}", type="primary"):
            db.execute(f"DELETE FROM {watchlist_table}")
            if item_type == 'stock':
                st.session_state.backtest_pool.clear()
            st.session_state.message = {"type": "success", "body": f"已清空所有自选{type_name}。"}
            st.rerun()
    else:
        st.info(f"您的自选{type_name}列表为空。" )

# --- Sidebar Navigation ---
st.sidebar.title("导航")
menu = ["数据管理", "自选列表管理", "资产管理", "选股策略", "指数对比", "回测引擎", "风险分析", "系统说明与操作指南"]
choice = st.sidebar.selectbox("功能导航", menu, key="main_menu")

display_status()

st.sidebar.divider()
if st.sidebar.button("退出系统"):
    st.balloons()
    st.success("感谢使用！您可以安全地关闭此浏览器标签页。" )
    st.stop()

# --- Page Content ---
st.title("WaySsystem - 量化交易管理系统")

if choice == "数据管理":
    st.header("数据管理")
    st.subheader("基础信息更新")
    st.info("首次使用或需要更新市场股票/指数列表时，请点击下方按钮。" )
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

elif choice == "自选列表管理":
    st.header("自选列表管理")
    stock_tab, index_tab = st.tabs(["自选股", "自选指数"])
    with stock_tab:
        render_watchlist_editor('stock')
    with index_tab:
        render_watchlist_editor('index')

elif choice == "资产管理":
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

elif choice == "选股策略":
    st.header("选股策略")
    strategy_name = st.selectbox("选择一个选股策略", list(sm.strategies.keys()))
    if st.button("开始选股", type="primary"):
        stocks = db.fetch_all("SELECT ts_code FROM watchlist")
        if not stocks:
            st.error("错误：您的自选股列表为空。请先在“自选列表管理”页面添加股票。" )
            st.stop()

        stock_codes = [stock['ts_code'] for stock in stocks]
        with st.spinner(f"正在对自选股池中的 {len(stock_codes)} 只股票运行 ‘{strategy_name}’ 策略..."):
            results = sm.run_screening(strategy_name, stock_codes)
            if results:
                st.success(f"策略运行完成，共筛选出 {len(results)} 只符合条件的股票。" )
                st.dataframe(pd.DataFrame(results))
            else:
                st.info("根据最新数据，您的自选股中没有找到符合该策略条件的股票。" )

elif choice == "指数对比":
    st.header("指数对比分析")
    st.info("本功能用于分析两个指数之间的相对强弱关系，通过计算每日收盘价比值来分析走势。")

    # 获取所有自选指数用于选择
    available_indices = db.fetch_all("SELECT ts_code, name FROM index_watchlist ORDER BY ts_code")
    if not available_indices:
        st.warning("您的自选指数列表为空。请先在“自选列表管理”页面添加指数（如 000985.CSI 和 857372.SI）并更新其数据。")
        st.stop()

    index_options = {f"{i['name']} ({i['ts_code']})": i['ts_code'] for i in available_indices}
    
    # 查找默认选项的索引
    try:
        default_base_index = list(index_options.values()).index('000985.CSI')
    except ValueError:
        default_base_index = 0
    try:
        default_industry_index = list(index_options.values()).index('857372.SI')
    except ValueError:
        default_industry_index = 1 if len(index_options) > 1 else 0


    col1, col2 = st.columns(2)
    with col1:
        base_selection = st.selectbox("选择基准指数 (如 全A指数)", options=index_options.keys(), index=default_base_index)
        base_index_code = index_options[base_selection]
    with col2:
        comparison_selection = st.selectbox("选择对比指数", options=index_options.keys(), index=default_industry_index)
        comparison_index_code = index_options[comparison_selection]

    date_range = st.date_input("选择分析时间周期", [date(2024, 1, 1), date.today()], key="comparison_date_range")

    if st.button("开始分析", type="primary"):
        if not date_range or len(date_range) != 2:
            st.error("请选择一个有效的日期范围。")
        elif base_index_code == comparison_index_code:
            st.error("基准指数和对比指数不能相同。")
        else:
            start_str, end_str = date_range[0].strftime('%Y%m%d'), date_range[1].strftime('%Y%m%d')
            with st.spinner(f"正在计算 {comparison_selection} 相对于 {base_selection} 的比值..."):
                result_df = compare_indices(db, base_index_code, comparison_index_code, start_str, end_str)
                
                if result_df is not None and not result_df.empty:
                    st.success("分析完成！")
                    
                    # 获取最新数据用于提示文字
                    latest_date = result_df['date'].max()
                    latest_ratio = result_df[result_df['date'] == latest_date]['ratio_c'].iloc[0]
                    latest_ma10 = result_df[result_df['date'] == latest_date]['c_ma10'].iloc[0] if not pd.isna(result_df[result_df['date'] == latest_date]['c_ma10'].iloc[0]) else "N/A"
                    latest_ma20 = result_df[result_df['date'] == latest_date]['c_ma20'].iloc[0] if not pd.isna(result_df[result_df['date'] == latest_date]['c_ma20'].iloc[0]) else "N/A"
                    latest_ma60 = result_df[result_df['date'] == latest_date]['c_ma60'].iloc[0] if not pd.isna(result_df[result_df['date'] == latest_date]['c_ma60'].iloc[0]) else "N/A"
                    
                    # 添加大盘走势提示
                    st.subheader("📊 大盘走势分析")
                    
                    # 获取沪深300最新数据
                    hs300_query = """
                    SELECT date, close FROM index_daily_price 
                    WHERE ts_code = '000300.SH' AND date <= ? 
                    ORDER BY date DESC LIMIT 1
                    """
                    hs300_latest = db.fetch_one(hs300_query, (end_str,))
                    
                    hs300_ma120_query = """
                    SELECT AVG(close) as ma120 FROM index_daily_price 
                    WHERE ts_code = '000300.SH' AND date <= ? 
                    ORDER BY date DESC LIMIT 120
                    """
                    hs300_ma120 = db.fetch_one(hs300_ma120_query, (end_str,))
                    
                    if hs300_latest and hs300_ma120:
                        st.info(f"**{latest_date.strftime('%Y年%m月%d日')}，沪深300指数收盘为{hs300_latest['close']:.2f}点，其120日均线点位为{hs300_ma120['ma120']:.2f}点，请自行判断大盘走势。**")
                    
                    st.subheader("📈 指数对比图表")
                    fig = px.line(result_df, x='date', y=['ratio_c', 'c_ma10', 'c_ma20', 'c_ma60'],
                                  title=f'{comparison_selection} vs {base_selection} 收盘价比值',
                                  labels={'value': '比值', 'date': '日期', 'variable': '指标'})
                    fig.update_layout(legend_title_text='指标图例')
                    fig.update_xaxes(
                        tickformat="%Y-%m-%d",
                        dtick="M1",
                        ticklabelmode="period"
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    st.subheader("📋 详细数据")
                    st.dataframe(result_df)
                else:
                    st.error("分析失败。可能的原因是：在选定时间段内，一个或两个指数缺少数据，或者数据无法对齐。请检查您的数据。")

elif choice == "回测引擎":
    st.header("回测引擎")
    st.subheader("回测参数设置")
    col1, col2 = st.columns(2)
    initial_capital = col1.number_input("初始资金", min_value=10000, value=1000000, step=10000, help="用于回测的起始现金总额。" )
    max_positions = col2.number_input("最大持仓股票数", min_value=1, value=5, step=1, help="允许同时持有的最大股票数量。" )
    
    strategy_name = st.selectbox("选择一个交易策略", list(sm.strategies.keys()))
    date_range = st.date_input("选择回测时间周期", [date(2024, 1, 1), date.today()], key="backtest_date_range")

    if date_range and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = date(2024, 1, 1), date.today()
        st.warning("日期范围选择不完整，已自动重置为默认值。" )

    st.divider()
    st.subheader("执行回测")

    backtest_pool = st.session_state.get('backtest_pool', set())
    if not backtest_pool:
        st.warning("您的回测池为空。请先在“自选列表管理”页面将股票加入回测池。" )
    else:
        st.success(f"当前回测池中有 {len(backtest_pool)} 只股票可供回测。" )
        with st.expander("查看回测池中的股票"):
            placeholders = ','.join('?' for _ in backtest_pool)
            query = f"SELECT ts_code, name FROM watchlist WHERE ts_code IN ({placeholders})"
            pool_details = db.fetch_all(query, tuple(backtest_pool))
            if pool_details:
                st.dataframe(pd.DataFrame(pool_details), hide_index=True)

        if st.button("开始回测", type="primary"):
            start_str, end_str = start_date.strftime('%Y%m%d'), end_date.strftime('%Y%m%d')
            with st.spinner(f"正在使用 Backtrader 引擎进行回测..."):
                result = run_backtest(strategy_name, list(backtest_pool), start_str, end_str, initial_capital, max_positions)
                
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
                else:
                    st.error("回测执行失败或没有产生任何结果。" )

elif choice == "风险分析":
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

elif choice == "系统说明与操作指南":
    st.header("系统说明与操作指南")
    st.markdown(get_guide_content())
