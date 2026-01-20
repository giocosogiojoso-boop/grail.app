import streamlit as st
import google.generativeai as genai
import requests
import feedparser
import urllib.parse
import datetime
import pytz
import yfinance as ticker_data
import plotly.graph_objects as go  # チャート描画用

# --- アプリ基本設定 ---
st.set_page_config(page_title="FX AI-Analyst 2026", page_icon="📈", layout="centered")

# --- 日本時間の取得 ---
def get_jst_now():
    jst = pytz.timezone('Asia/Tokyo')
    return datetime.datetime.now(jst)

# --- レート & チャートデータ取得 ---
@st.cache_data(ttl=60)
def get_fx_data(interval="1d"):
    # interval: 1h(時間足), 1d(日足), 1wk(週足)
    data = ticker_data.Ticker("JPY=X")
    # 期間を調整
    period = "2d" if interval=="1h" else "60d" if interval=="1d" else "250d"
    df = data.history(period=period, interval=interval)
    return df

# --- AIモデル取得 ---
def get_ai_model():
    if "GEMINI_API_KEY" not in st.secrets: return None, None
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model_names = ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-pro']
    for m_name in model_names:
        try: return genai.GenerativeModel(m_name), m_name
        except: continue
    return None, None

# --- ニュース取得 ---
@st.cache_data(ttl=300)
def get_latest_forex_news():
    news_list = []
    search_query = 'USD JPY "forex" OR "円安" OR "円高" when:1d'
    encoded_query = urllib.parse.quote(search_query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"
    try:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:10]: news_list.append(f"・{entry.title}")
    except: pass
    return news_list

# --- UI構築 ---
st.title("📈 ドル円 AI実戦司令塔")

# ステータス表示
jst_now = get_jst_now()
df_now = get_fx_data("1d")
current_rate = round(df_now['Close'].iloc[-1], 3) if not df_now.empty else None

col1, col2 = st.columns(2)
with col1:
    st.metric("現在時刻 (日本)", jst_now.strftime('%Y/%m/%d %H:%M'))
with col2:
    st.metric("USD / JPY", f"{current_rate} 円" if current_rate else "取得エラー")

# --- チャートエリア ---
# 表示する足の種類をセッションで管理
if 'chart_interval' not in st.session_state:
    st.session_state.chart_interval = "1d"

# チャートデータの取得
df_chart = get_fx_data(st.session_state.chart_interval)

# Plotlyでローソク足作成
fig = go.Figure(data=[go.Candlestick(
    x=df_chart.index,
    open=df_chart['Open'],
    high=df_chart['High'],
    low=df_chart['Low'],
    close=df_chart['Close'],
    increasing_line_color='#00ff00', decreasing_line_color='#ff0000'
)])
fig.update_layout(
    height=400, margin=dict(l=10, r=10, b=10, t=10),
    xaxis_rangeslider_visible=False,
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
    yaxis=dict(gridcolor='gray')
)
st.plotly_chart(fig, use_container_width=True)

# チャート右下にボタン配置
c1, c2, c3, c4 = st.columns([4, 1, 1, 1])
with c2:
    if st.button("時間"): st.session_state.chart_interval = "1h"; st.rerun()
with c3:
    if st.button("日足"): st.session_state.chart_interval = "1d"; st.rerun()
with c4:
    if st.button("週足"): st.session_state.chart_interval = "1wk"; st.rerun()

st.divider()

# 解析ボタン
if st.button("最新相場を1クリック解析", use_container_width=True, type="primary"):
    with st.spinner("AI分析中..."):
        model, m_name = get_ai_model()
        news = get_latest_forex_news()
        if model:
            prompt = f"現在は2026年1月、日本時間は{jst_now.strftime('%H:%M')}、レートは{current_rate}円。ニュースに基づき分析せよ。\n\n【ニュース】\n" + "\n".join(news)
            response = model.generate_content(prompt)
            st.success(f"解析完了 ({m_name})")
            st.markdown(response.text)

with st.sidebar:
    st.header("資金管理")
    balance = st.number_input("残高", value=1000000)
    risk = st.slider("リスク%", 0.1, 5.0, 1.0)
    st.metric("許容損失額", f"{int(balance * risk / 100):,} 円")
