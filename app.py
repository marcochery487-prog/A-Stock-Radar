import streamlit as st
import pandas as pd
import requests
import time

# 页面基础配置
st.set_page_config(page_title="全自动选股 · 云端旗舰直连版", layout="wide")

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

# 云端裸连东财底层接口 (不写本地文件，无视权限报错)
def fetch_market_data():
    url = "http://8.push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": "6000", "po": "1", "np": "1", "fltt": "2", "invt": "2", "fid": "f3",
        "fs": "m:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23,m:0 t:81 s:2048",
        "fields": "f12,f14,f2,f3,f10,f8,f6"
    }
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        res = requests.get(url, params=params, headers=headers, timeout=10)
        if res.status_code != 200: return None, f"HTTP报错 {res.status_code}"
        data = res.json()
        items = data.get("data", {}).get("diff", [])
        if not items: return None, "数据返回为空"
        
        df = pd.DataFrame(items)
        rename_map = {"f12": "股票代码", "f14": "股票名称", "f2": "最新价", "f3": "涨跌幅", "f10": "量比", "f8": "换手率", "f6": "成交额"}
        df = df.rename(columns=rename_map)
        
        for col in ['最新价', '涨跌幅', '量比', '换手率', '成交额']:
            df[col] = pd.to_numeric(df[col].replace('-', '0'), errors='coerce').fillna(0)
        df['股票代码'] = df['股票代码'].astype(str).str.zfill(6)
        
        return df, "⚡ 云端底层专线直连"
    except Exception as e:
        return None, f"请求异常: {str(e)[:40]}"

# --- 界面布局 ---
st.title("🎯 全自动选股 · 云端旗舰直连版")

# 初始化状态
for key in ['base_pool', 'auction_pool', 'alert_pool', 'top8_pool']:
    if key not in st.session_state: st.session_state[key] = pd.DataFrame()

with st.sidebar:
    st.header("🕹️ 控制台")
    if st.button("🚀 强制全流程刷新", use_container_width=True):
        with st.spinner("云服务器正在秒拉全市场行情..."):
            snap, node = fetch_market_data()
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
                st.success(f"更新成功！数据源: {node}")
            else:
                st.error(f"拉取失败，原因: {node}")

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
