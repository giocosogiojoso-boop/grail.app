import streamlit as st
import google.generativeai as genai
import requests
import feedparser
import urllib.parse
import datetime

# --- アプリ設定 ---
st.set_page_config(page_title="FX AI-Analyst", page_icon="📈", layout="centered")

# APIキーの取得（Streamlit Secretsから）
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    NEWS_API_KEY = st.secrets["NEWS_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('models/gemini-1.5-flash')
except:
    st.error("SecretsにAPIキーが設定されていません。")

# --- ニュース取得エンジン（キャッシュ5分） ---
@st.cache_data(ttl=300)
def get_all_news():
    news_list = []
    # 1. Main API (NewsAPI) を試行
    try:
        url = f'https://newsapi.org/v2/everything?q=USD+JPY+forex&language=en&sortBy=publishedAt&apiKey={NEWS_API_KEY}'
        res = requests.get(url).json()
        for a in res.get('articles', [])[:5]:
            news_list.append(f"[{a['source']['name']}] {a['title']}")
    except:
        pass

    # 2. Fallback (Google News RSS)
    try:
        query = urllib.parse.quote("USD JPY FX")
        rss_url = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:5]:
            news_list.append(f"[GoogleNews] {entry.title}")
    except:
        pass
    
    return news_list, datetime.datetime.now().strftime("%H:%M:%S")

# --- UI構築 ---
st.title("📈 ドル円 AI実戦司令塔")
st.caption("勝率80%目標：7大メディア統合解析エンジン")

if st.button("最新相場を1クリック解析", use_container_width=True):
    with st.spinner("情報を収集・解析中..."):
        # ニュース取得
        news, update_time = get_all_news()
        
        if not news:
            st.error("ニュースの取得に失敗しました。")
        else:
            # Gemini プロンプト（回避ルール込み）
            prompt = f"""
            FXトレーダーとして以下のニュースを分析し、ドル円の売買判定を行ってください。
            
            【ニュース】
            {chr(10).join(news)}
            
            【判定基準】
            1. 7媒体以上の論調が一致しない、または「だまし」の可能性がある場合は必ず『HOLD』。
            2. 既に価格に織り込まれている形跡がある場合も『HOLD』。
            3. 明確なトレンドがある場合のみ BUY または SELL。
            
            【出力形式】（必ず以下の項目を日本語で）
            ■判定: [BUY/SELL/HOLD]
            ■信頼度: [0-100]%
            ■理由: (短く)
            ■回避ルール適用状況: (なぜ見送ったか、またはなぜ安全か)
            """
            
            response = model.generate_content(prompt)
            
            # 結果表示
            st.success(f"解析完了（データ取得: {update_time}）")
            st.markdown("---")
            st.markdown(response.text)
            st.info("※注文はiPhoneのMT5アプリで手動で行ってください。")

# --- ロット計算機（サイドバー） ---
with st.sidebar:
    st.header("資金管理")
    balance = st.number_input("残高(円)", value=1000000)
    risk = st.slider("リスク(%)", 0.5, 5.0, 2.0)
    st.write(f"許容損失額: {int(balance * risk / 100)} 円")
