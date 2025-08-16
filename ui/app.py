import os
import sys
import logging
import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.ui_helpers import init_state, show_status_panel

st.set_page_config(page_title="streamlit-股票分析系统", page_icon="📈", layout="wide")
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')

init_state()
show_status_panel()

st.title("streamlit-股票分析系统")
st.write("欢迎使用。请从左侧页面选择功能模块进行操作。")

st.sidebar.divider()
if st.sidebar.button("退出系统"):
    st.balloons()
    st.success("感谢使用！您可以安全地关闭此浏览器标签页。")
    st.stop()
