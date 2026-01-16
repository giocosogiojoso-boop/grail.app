import streamlit as st
import google.generativeai as genai

st.title("FX AI 接続テスト")

# API設定
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # モデル名を 'gemini-1.5-flash' に固定
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
else:
    st.error("Secretsにキーが見つかりません")

if st.button("テスト解析開始"):
    try:
        response = model.generate_content("今日のドル円相場について一言で予測して")
        st.write(response.text)
        st.success("通信成功！")
    except Exception as e:
        st.error(f"エラー発生: {e}")
