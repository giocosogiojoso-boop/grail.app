import streamlit as st
import google.generativeai as genai
import requests
import feedparser
import urllib.parse
import datetime
import yfinance as ticker_data  # レート取得用

# --- アプリ基本設定 ---
st.set_page_config(page_title="FX AI-Analyst 2026", page_icon="📈", layout="centered")

# --- 最新レート取得関数 ---
def get_current_usd_jpy():
    try:
        # yfinanceを使ってドル円(JPY=X)の最新データを取得
        data = ticker_data.Ticker("JPY=X")
        price = data.history(period="1d")['Close'].iloc[-1]
        return round(price, 3)
    except:
        return None

# --- AIモデル取得ロジック ---
def get_ai_model():
    if "GEMINI_API_KEY" not in st.secrets:
        return None, None
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model_names = ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-pro']
    for m_name in model_names:
        try:
            return genai.GenerativeModel(m_name), m_name
        except:
            continue
    return None, None

# --- ニュース取得エンジン ---
@st.cache_data(ttl=300)
def get_latest_forex_news():
    news_list = []
    search_query = 'USD JPY "forex" OR "円安" OR "円高" when:1d'
    encoded_query = urllib.parse.quote(search_query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"
    try:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:10]:
            news_list.append(f"【{entry.get('published', '')}】 {entry.title}")
    except:
        pass
    return news_list

# --- UI構築 ---
st.title("📈 ドル円 AI実戦司令塔")

# --- ステータスパネル (日時 & レート) ---
now = datetime.datetime.now()
current_rate = get_current_usd_jpy()

# 2カラムで日時とレートを綺麗に表示
col1, col2 = st.columns(2)
with col1:
    st.metric("現在時刻", now.strftime('%Y/%m/%d %H:%M'))
with col2:
    if current_rate:
        st.metric("USD / JPY", f"{current_rate} 円")
    else:
        st.metric("USD / JPY", "取得エラー")

st.divider()

# メイン解析ボタン
if st.button("最新相場を1クリック解析", use_container_width=True, type="primary"):
    with st.spinner("2026年最新情報をスキャン中..."):
        model, model_name = get_ai_model()
        news_data = get_latest_forex_news()
        
        if model and news_data:
            prompt = f"""
            現在は2026年1月、ドル円レートは {current_rate} 円付近です。
            高市政権下の最新ニュースに基づき、プロトレーダーとして分析してください。
            1. 古い情報は無視。
            2. 高市氏は現職の総理。
            3. 慎重に判定。

            【ニュース】
            {chr(10).join(news_data)}
            """
            try:
                response = model.generate_content(prompt)
                st.success(f"解析完了 (AI: {model_name})")
                st.markdown("---")
                st.markdown(response.text)
                with st.expander("情報ソースを確認"):
                    for n in news_data: st.write(n)
            except Exception as e:
                st.error(f"解析エラー: {e}")

# --- サイドバー：資金管理 ---
with st.sidebar:
    st.header("資金管理")
    balance = st.number_input("運用残高(円)", value=1000000, step=10000)
    risk_rate = st.slider("許容リスク(%)", 0.1, 5.0, 1.0)
    st.metric("最大許容損失額", f"{int(balance * risk_rate / 100):,} 円")
