import streamlit as st
import google.generativeai as genai
import requests
import feedparser
import urllib.parse
import datetime

# --- アプリ設定 ---
st.set_page_config(page_title="FX AI-Analyst", page_icon="📈")

# --- 接続成功したモデル設定を統合 ---
def get_ai_model():
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # 接続が確認できた gemini-2.5-flash を優先的に使用
    for m_name in ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-pro']:
        try:
            return genai.GenerativeModel(m_name), m_name
        except:
            continue
    return None, None

# --- ニュース取得エンジン ---
@st.cache_data(ttl=300)
def get_forex_news():
    news_list = []
    # Google News RSS (ドル円関連)
    try:
        query = urllib.parse.quote("USD JPY FX news")
        rss_url = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:8]:
            news_list.append(f"・{entry.title}")
    except:
        pass
    return news_list

# --- UI構築 ---
st.title("📈 ドル円 AI実戦司令塔")
st.caption("最新ニュースに基づく統合解析エンジン")

if st.button("最新相場を1クリック解析", use_container_width=True):
    with st.spinner("世界中のニュースを収集中..."):
        model, model_name = get_ai_model()
        news = get_forex_news()
        
        if model and news:
            prompt = f"""
            プロのFXトレーダーとして、以下の最新ニュースからドル円の今後の展開を分析してください。
            
            【ニュース材料】
            {chr(10).join(news)}
            
            【出力形式】
            ■判定: [BUY/SELL/HOLD]
            ■信頼度: [0-100]%
            ■理由: (短く簡潔に)
            ■警戒材料: (だましを避けるための注意点)
            """
            
            try:
                response = model.generate_content(prompt)
                st.success(f"解析完了 (使用AI: {model_name})")
                st.markdown("---")
                st.markdown(response.text)
            except Exception as e:
                st.error(f"解析中にエラーが発生しました: {e}")
        else:
            st.error("データの取得に失敗しました。")

# --- サイドバー：資金管理ツール ---
with st.sidebar:
    st.header("資金管理ツール")
    balance = st.number_input("証拠金(円)", value=1000000)
    risk_pct = st.slider("許容リスク(%)", 0.5, 5.0, 2.0)
    st.info(f"今回の許容損失額: {int(balance * risk_pct / 100):,} 円")
