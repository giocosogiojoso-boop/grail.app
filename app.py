import streamlit as st
import google.generativeai as genai

st.title("FX AI 接続テスト")

# API設定
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # モデル名を 'gemini-1.5-flash' に固定
    model = try:
    # 案1: まずは標準の1.5-flashを試す
    model = genai.GenerativeModel('gemini-1.5-flash')
    # 通信テスト用のダミー実行（ここでエラーなら案2へ）
    model.generate_content("test") 
except:
    try:
        # 案2: 1.5がダメなら、より汎用的な 1.0-pro を試す
        model = genai.GenerativeModel('gemini-pro')
    except:
        # 案3: 最終手段。利用可能な最初のモデルを自動で選ぶ
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        model = genai.GenerativeModel(models[0])
else:
    st.error("Secretsにキーが見つかりません")

if st.button("テスト解析開始"):
    try:
        response = model.generate_content("今日のドル円相場について一言で予測して")
        st.write(response.text)
        st.success("通信成功！")
    except Exception as e:
        st.error(f"エラー発生: {e}")
