import streamlit as st
import pandas as pd
import efinance as ef
import akshare as ak
import time

# 页面基础配置
st.set_page_config(page_title="A股尾盘点火狙击终端", layout="wide")

# 核心列配置
COLUMN_CONFIG = {
    "最新价": st.column_config.NumberColumn(format="%.2f"),
    "涨跌幅": st.column_config.NumberColumn(format="%.2f%%"),
    "量比": st.column_config.NumberColumn(format="%.2f"),
    "换手率": st.column_config.NumberColumn(format="%.2f%%"),
    "成交额": st.column_config.NumberColumn(format="%.0f"),
}
DISPLAY_COLS = ['股票代码', '股票名称', '最新价', '涨跌幅', '量比', '换手率', '成交额']

# 数据颜色渲染逻辑
def color_rules(val):
    try:
        num = float(str(val).replace('%', ''))
        if num > 0: return 'color: red; font-weight: bold;'
        elif num < 0: return 'color: green;'
        return ''
    except: return ''

def safe_style_df(df):
    if df is None or df.empty: return pd.DataFrame()
    cols = [c for c in DISPLAY_COLS if c in df.columns]
    temp_df = df[cols].copy()
    return temp_df.style.map(color_rules, subset=['涨跌幅'])

# 统一数据清洗逻辑
def clean_data(df, source):
    if df is None or df.empty: return None
    if source == "ak":
        df = df.rename(columns={'代码': '股票代码', '名称': '股票名称', '涨跌幅': '涨幅'})
    if '涨幅' in df.columns and '涨跌幅' not in df.columns:
        df = df.rename(columns={'涨幅': '涨跌幅'})
    
    df['股票代码'] = df['股票代码'].astype(str).str.strip().str.zfill(6)
    for col in ['最新价', '涨跌幅', '量比', '换手率', '成交额']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace('%',''), errors='coerce').fillna(0)
    return df

# 双核抓取引擎
def get_market_snapshot():
    try:
        df = ef.stock.get_realtime_quotes()
        if df is not None and not df.empty: return clean_data(df, "ef"), "⚡ 云端高速节点 (ef)"
    except: pass
    try:
        df = ak.stock_zh_a_spot_em()
        if df is not None and not df.empty: return clean_data(df, "ak"), "🛡️ 云端备用节点 (ak)"
    except: pass
    return None, "❌ 获取失败"

# --- 界面布局 ---
st.title("🎯 全自动选股 · 云端旗舰版")

# 初始化状态
for key in ['base_pool', 'auction_pool', 'alert_pool', 'top8_pool']:
    if key not in st.session_state: st.session_state[key] = pd.DataFrame()

with st.sidebar:
    st.header("🕹️ 控制台")
    if st.button("🚀 强制全流程刷新", use_container_width=True):
        with st.spinner("云服务器正在穿透获取全市场行情..."):
            snap, node = get_market_snapshot()
            if snap is not None:
                # 过滤逻辑：主板 + 非ST + 5元以上
                base = snap[snap['股票代码'].str.startswith(('00', '60')) & (~snap['股票名称'].str.contains('ST')) & (snap['最新价'] > 5)]
                # 竞价池：量比>1.8 且 红盘
                auc = base[(base['量比'] > 1.8) & (base['涨跌幅'] > 0)]
                # 点火雷达：3% - 8%
                alert = auc[(auc['涨跌幅'] > 3) & (auc['涨跌幅'] <= 8)]
                
                st.session_state.base_pool = base.head(15)
                st.session_state.auction_pool = auc.head(15)
                st.session_state.alert_pool = alert
                if not alert.empty:
                    st.session_state.top8_pool = alert.sort_values(by='成交额', ascending=False).head(8)
                st.sidebar.success(f"更新成功！来源: {node}")
            else:
                st.sidebar.error("云端拉取异常，请稍后重试。")

# 渲染数据表格
c1, c2 = st.columns(2)
with c1:
    st.subheader("📦 主板底座状态")
    st.dataframe(safe_style_df(st.session_state.base_pool), column_config=COLUMN_CONFIG, use_container_width=True)
with c2:
    st.subheader("🔥 竞价达标 (量比>1.8)")
    st.dataframe(safe_style_df(st.session_state.auction_pool), column_config=COLUMN_CONFIG, use_container_width=True)

st.markdown("---")
st.subheader("🚨 实时点火预警 (3%-8% 狙击区间)")
st.dataframe(safe_style_df(st.session_state.alert_pool), column_config=COLUMN_CONFIG, height=350, use_container_width=True)

st.markdown("---")
st.subheader("🏆 尾盘核心狙击区 (Top 8)")
if not st.session_state.top8_pool.empty:
    st.dataframe(safe_style_df(st.session_state.top8_pool), column_config=COLUMN_CONFIG, use_container_width=True)
else:
    st.info("等待雷达扫描信号...")
