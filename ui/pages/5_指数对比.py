import os
import sys
from datetime import date
import streamlit as st
import pandas as pd
import plotly.express as px

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.ui_helpers import init_state, show_status_panel
from analysis.market_comparison import compare_indices

init_state()
show_status_panel()

db = st.session_state.db

st.header("指数对比分析")
st.info("先选择基准和参与对比的指数，点击“开始对比”。之后可用“上一个/下一个”在所选列表中轮播并自动对比。")

available_indices = db.fetch_all("SELECT ts_code, name FROM index_watchlist ORDER BY ts_code")
if not available_indices:
    st.warning("您的自选指数列表为空。请先在“自选列表管理”页面添加指数并更新其数据。")
    st.stop()

index_options = {f"{i['name']} ({i['ts_code']})": i['ts_code'] for i in available_indices}
label_by_code = {v: k for k, v in index_options.items()}

try:
    default_base_index = list(index_options.values()).index('000985.CSI')
except ValueError:
    default_base_index = 0

col1, col2 = st.columns([2, 1])
with col1:
    base_selection = st.selectbox("选择基准指数", options=list(index_options.keys()), index=default_base_index, key="base_index_select")
    base_index_code = index_options[base_selection]
with col2:
    date_range = st.date_input("时间周期", [date(2024, 1, 1), date.today()], key="comparison_date_range")

# 基准变化时，重置轮播状态与已选择列表
if st.session_state.get('carousel_base_code') != base_index_code:
    st.session_state['carousel_base_code'] = base_index_code
    st.session_state['idx_compare_codes'] = []
    st.session_state['idx_compare_labels'] = []
    st.session_state['carousel_pos'] = 0
    st.session_state['carousel_started'] = False

# 多选参与对比的指数（排除基准）
available_labels = [lbl for lbl, code in index_options.items() if code != base_index_code]
default_selected = st.session_state.get('idx_compare_labels', [])
selected_labels = st.multiselect("选择参与对比的指数（可多选）", options=available_labels, default=default_selected)

st.divider()
if not date_range or len(date_range) != 2:
    st.error("请选择一个有效的日期范围。")
elif st.button("开始对比", type="primary"):
    selected_codes = [index_options[lbl] for lbl in selected_labels if index_options.get(lbl) != base_index_code]
    if not selected_codes:
        st.warning("请至少选择一个参与对比的指数。")
    else:
        st.session_state['idx_compare_codes'] = selected_codes
        st.session_state['idx_compare_labels'] = selected_labels
        st.session_state['carousel_pos'] = 0
        st.session_state['carousel_started'] = True
        st.rerun()

# 若已开始对比：展示轮播并自动计算
if st.session_state.get('carousel_started'):
    codes = st.session_state.get('idx_compare_codes', [])
    if not codes:
        st.info("未选择参与对比的指数，请先上方多选并点击开始对比。")
    else:
        pos = st.session_state.get('carousel_pos', 0)
        pos = max(0, min(pos, len(codes) - 1))
        comparison_index_code = codes[pos]
        comparison_label = label_by_code.get(comparison_index_code, comparison_index_code)

        prev_col, disp_col, next_col = st.columns([1, 3, 1])
        with prev_col:
            if st.button("上一个", use_container_width=True):
                st.session_state['carousel_pos'] = (pos - 1) % len(codes)
                st.rerun()
        with disp_col:
            st.markdown(f"当前对比：**{comparison_label}**（{pos+1}/{len(codes)}）")
        with next_col:
            if st.button("下一个", use_container_width=True):
                st.session_state['carousel_pos'] = (pos + 1) % len(codes)
                st.rerun()

        start_str, end_str = date_range[0].strftime('%Y%m%d'), date_range[1].strftime('%Y%m%d')
        with st.spinner(f"正在计算 {comparison_label} 相对于 {base_selection} 的比值..."):
            result_df = compare_indices(db, base_index_code, comparison_index_code, start_str, end_str)
            if result_df is not None and not result_df.empty:
                latest_date = result_df['date'].max()
                latest_ratio = result_df[result_df['date'] == latest_date]['ratio_c'].iloc[0]
                latest_ma10 = result_df[result_df['date'] == latest_date]['c_ma10'].iloc[0] if 'c_ma10' in result_df.columns else None
                if pd.notna(latest_ma10):
                    st.info(f"截至 {latest_date.strftime('%Y年%m月%d日')}，比值为 {latest_ratio:.3f}，MA10 为 {latest_ma10:.3f}。")
                fig = px.line(result_df, x='date', y=['ratio_c', 'c_ma10', 'c_ma20', 'c_ma60'],
                              title=f'{comparison_label} vs {base_selection} 收盘价比值',
                              labels={'value': '比值', 'date': '日期', 'variable': '指标'})
                fig.update_layout(legend_title_text='指标图例')
                fig.update_xaxes(tickformat="%Y-%m-%d", dtick="M1", ticklabelmode="period")
                st.plotly_chart(fig, use_container_width=True)
                st.subheader("📋 详细数据")
                st.dataframe(result_df)
            else:
                st.error("分析失败。可能是选定时间段内一个或两个指数缺少数据，或数据无法对齐。")
else:
    st.info("选择好基准与参与对比的指数后，点击上方“开始对比”。")

