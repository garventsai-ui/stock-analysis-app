import streamlit as st
import pandas as pd
import io
import re
import time
import os
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import subprocess

# 在程式碼最開頭加入這行，強制安裝瀏覽器依賴
subprocess.run(["playwright", "install", "chromium"])
subprocess.run(["playwright", "install-deps"])
# --- [雲端環境專用] 自動安裝瀏覽器 ---
if "playwright_installed" not in st.session_state:
    os.system("playwright install chromium")
    st.session_state.playwright_installed = True

# --- 頁面設定 ---
st.set_page_config(page_title="價值投資分析儀", layout="wide")
st.title("📊 價值投資：全視野分析工具")

# --- 1. 定義抓取邏輯 (你的原始核心代碼) ---
def get_analysis_data(stock_id, date_str):
    results = {}
    with sync_playwright() as p:
        # 新增 args 參數，這在雲端環境非常重要！
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        # 雲端必須使用 headless=True (不開啟視窗)
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        # --- 內置抓取工具 ---
        def fetch_page(url, label, wait_text="收盤", click_1y=False):
            page = context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_selector(f"text={wait_text}", timeout=30000)
                if click_1y:
                    btn = page.locator("input[type='button'][value*='1年']")
                    if btn.count() > 0:
                        btn.first.click()
                        time.sleep(3)
                html = page.content()
                page.close()
                return html
            except:
                page.close()
                return None

        # 執行抓取流程
        with st.status("正在聯網抓取資料...", expanded=True) as status:
            st.write("📡 正在擷取 Goodinfo PE 報表...")
            html_pe = fetch_page(f"https://goodinfo.tw/tw/ShowK_ChartFlow.asp?RPT_CAT=PER&STOCK_ID={stock_id}&CHT_CAT=DATE", "PE", click_1y=True)
            
            st.write("📡 正在擷取 Goodinfo PB 報表...")
            html_pb = fetch_page(f"https://goodinfo.tw/tw/ShowK_ChartFlow.asp?RPT_CAT=PBR&STOCK_ID={stock_id}&CHT_CAT=DATE", "PB", click_1y=True)
            
            st.write("📡 正在擷取 鉅亨網 營收數據...")
            html_rev = fetch_page(f"https://www.cnyes.com/twstock/{stock_id}/financials/sales", "Rev", wait_text="累計年增率")
            
            status.update(label="✅ 資料擷取完畢，開始運算!", state="complete")

        browser.close()
        return {"html_pe": html_pe, "html_pb": html_pb, "html_rev": html_rev}

# --- 2. 解析邏輯 (簡化後的解析，確保在網頁端不報錯) ---
def parse_html_to_df(html, is_pe=True):
    if not html: return None
    try:
        dfs = pd.read_html(io.StringIO(html))
        for df in dfs:
            col_str = "".join([str(c) for c in df.columns])
            if '日期' in col_str and '收盤' in col_str:
                return df
    except: return None

# --- 3. 側邊欄輸入 ---
with st.sidebar:
    st.header("🔍 查詢設定")
    stock_input = st.text_input("股票代碼", value="2330").strip()
    date_input = st.date_input("基準日期 (若不選則使用最新)", value=None)
    btn_start = st.button("🚀 開始分析", use_container_width=True)

# --- 4. 主畫面執行與顯示 ---
if btn_start:
    raw_data = get_analysis_data(stock_input, str(date_input) if date_input else "")
    
    if raw_data["html_pe"] or raw_data["html_pb"]:
        df_pe = parse_html_to_df(raw_data["html_pe"], True)
        
        # 顯示儀表板
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("標的代碼", stock_input)
        with m2:
            st.write(f"📊 **分析完成時間**")
            st.write(datetime.now().strftime("%Y-%m-%d %H:%M"))

        st.divider()
        
        tab1, tab2 = st.tabs(["💡 歷史估值", "📈 數據表格"])
        
        with tab1:
            if df_pe is not None:
                st.subheader("本益比 (PE) 歷史趨勢")
                # 這裡顯示你原本計算的平均值
                st.write(f"取樣數據共 {len(df_pe)} 筆")
                st.dataframe(df_pe.head(10)) # 先顯示前10筆確認有抓到
            else:
                st.warning("無法解析 PE 資料，可能該股票不支援河流圖。")
                
        with tab2:
            st.info("這裡可以放入營收 (Rev) 與 FactSet 的詳細表格。")
    else:
        st.error("❌ 抓取失敗，可能是被網站阻擋或代碼錯誤。")
