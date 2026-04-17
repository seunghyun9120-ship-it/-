import streamlit as st
import os, json, datetime, re, time
from openai import OpenAI
from dotenv import load_dotenv

# 라이브러리 체크
try:
    from duckduckgo_search import DDGS
    DDG_AVAILABLE = True
except ImportError:
    DDG_AVAILABLE = False

load_dotenv()

# --- API KEY 설정 ---
if "GROQ_API_KEY" in st.secrets:
    api_key = st.secrets["GROQ_API_KEY"]
else:
    api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    st.error("❌ API 키를 찾을 수 없습니다.")
    st.stop()

client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key)
MODEL = "llama-3.3-70b-versatile"

# --- 초기 페르소나 설정 ---
FIXED_PERSONAS = [
    {"id":"aria",   "name":"Aria",   "color":"#E53935","emoji":"🔥","desc":"냉혹한 현실주의자","personality":"냉혹한 현실주의자. 결과와 효율 중심.","active":True},
    {"id":"marcus", "name":"Marcus", "color":"#1565C0","emoji":"🏛️","desc":"강경 보수주의자",  "personality":"전통과 질서 중시. 권위적 말투.","active":True},
    {"id":"zoe",    "name":"Zoe",    "color":"#2E7D32","emoji":"✊","desc":"급진적 진보주의자","personality":"혁명과 변화 갈망. 열정적 말투.","active":True},
    {"id":"jin",    "name":"Jin",    "color":"#7B1FA2","emoji":"🎯","desc":"극단적 허무주의자","personality":"모든 것은 무의미함. 건조하고 냉소적.","active":False},
    {"id":"mia",    "name":"Mia",    "color":"#E65100","emoji":"⚡","desc":"극단적 낙관주의자","personality":"기술이 모든 걸 해결함. 에너지 넘침.","active":False},
]

# --- 세션 관리 ---
if "personas" not in st.session_state:
    st.session_state.personas = [dict(p) for p in FIXED_PERSONAS]
if "history" not in st.session_state: st.session_state.history = []

# --- AI 응답 (과부하 방지 로직) ---
def ask_one(persona, history, web_data="", idx=0):
    # 요청 간격을 0.8초로 늘려 안정성 확보
    time.sleep(idx * 0.8) 
    
    system = (f"당신은 {persona['name']}입니다. {persona['personality']}\n"
              f"3~4문장 한국어로 답변하세요. 데이터: {web_data}")
    
    messages = [{"role":"system","content":system}]
    for turn in history[-3:]:
        messages.append({"role":"user","content":turn["user"]})
        if persona["name"] in turn["responses"]:
            messages.append({"role":"assistant","content":turn["responses"][persona["name"]]})

    try:
        res = client.chat.completions.create(model=MODEL, messages=messages, temperature=0.8)
        return persona["name"], res.choices[0].message.content
    except Exception as e:
        if "429" in str(e): return persona["name"], "⏳ (서버 부하로 대기 중... 잠시 후 다시 메시지를 보내주세요.)"
        return persona["name"], f"오류: {str(e)[:20]}"

# --- UI 설정 ---
st.set_page_config(page_title="AI 대화방", layout="centered")

# 사이드바: 캐릭터 추가 및 초기화
with st.sidebar:
    st.header("👥 대화 상대 관리")
    with st.expander("➕ 새 캐릭터 추가"):
        new_name = st.text_input("이름")
        new_desc = st.text_input("한줄 설명")
        new_pers = st.text_area("상세 성격")
        if st.button("추가하기"):
            if new_name and new_pers:
                st.session_state.personas.append({
                    "id": new_name.lower(), "name": new_name, "color": "#555", "emoji": "👤",
                    "desc": new_desc, "personality": new_pers, "active": True
                })
                st.rerun()
    
    if st.button("🔄 대화 내용 초기화", use_container_width=True):
        st.session_state.history = []; st.rerun()

st.title("💬 AI 단체 채팅")

# 캐릭터 선택 영역
st.write("대화 상대 선택 (최대 3~4명 권장)")
cols = st.columns(len(st.session_state.personas))
for i, p in enumerate(st.session_state.personas):
    with cols[i]:
        if st.button(f"{p['emoji']}\n{p['name']}", type="primary" if p["active"] else "secondary", key=f"p_{i}"):
            st.session_state.personas[i]["active"] = not p["active"]
            st.rerun()

st.divider()

# 대화 내용 출력
for turn in st.session_state.history:
    with st.chat_message("user"): st.write(turn["user"])
    for p_name, ans in turn["responses"].items():
        p_data = next((x for x in st.session_state.personas if x["name"] == p_name), {"emoji":"👤", "color":"#555"})
        with st.chat_message(p_name, avatar=p_data["emoji"]):
            st.markdown(f"**{p_name}**: {ans}")

# 입력창
if prompt := st.chat_input("메시지를 입력하세요..."):
    active_p = [p for p in st.session_state.personas if p["active"]]
    if not active_p:
        st.warning("대화 상대를 선택해주세요.")
    else:
        st.session_state.history.append({"user": prompt, "responses": {}})
        with st.spinner("AI들이 답변을 준비하고 있습니다..."):
            # 응답 생성
            res_dict = {}
            for i, p in enumerate(active_p):
                name, text = ask_one(p, st.session_state.history, "", i)
                res_dict[name] = text
            st.session_state.history[-1]["responses"] = res_dict
        st.rerun()
