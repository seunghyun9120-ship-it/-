import streamlit as st
import os, json, datetime, time
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# --- API KEY 설정 ---
if "GROQ_API_KEY" in st.secrets:
    api_key = st.secrets["GROQ_API_KEY"]
else:
    api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    st.error("❌ API 키를 찾을 수 없습니다. Streamlit Secrets 설정을 확인하세요.")
    st.stop()

client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key)
MODEL = "llama-3.1-8b-instant"

# --- 초기 페르소나 설정 ---
FIXED_PERSONAS = [
    {"id":"aria",   "name":"Aria",   "color":"#E53935","emoji":"🔥","desc":"현실주의","personality":"냉혹한 현실주의자. 효율과 결과 중심.","active":True},
    {"id":"marcus", "name":"Marcus", "color":"#1565C0","emoji":"🏛️","desc":"보수주의","personality":"전통과 질서 중시. 권위적 말투.","active":True},
    {"id":"zoe",    "name":"Zoe",    "color":"#2E7D32","emoji":"✊","desc":"진보주의","personality":"혁명과 변화 갈망. 열정적 말투.","active":True},
    {"id":"jin",    "name":"Jin",    "color":"#7B1FA2","emoji":"🎯","desc":"허무주의","personality":"모든 것은 무의미함. 냉소적 말투.","active":False},
    {"id":"mia",    "name":"Mia",    "color":"#E65100","emoji":"⚡","desc":"낙관주의","personality":"기술 만능주의. 에너지 넘치는 말투.","active":False},
]

# --- 세션 관리 ---
if "personas" not in st.session_state:
    st.session_state.personas = [dict(p) for p in FIXED_PERSONAS]
if "history" not in st.session_state: st.session_state.history = []

# --- AI 응답 함수 ---
def ask_one(persona, history, idx=0):
    time.sleep(idx * 0.2) 
    system = f"당신은 {persona['name']}입니다. {persona['personality']} 2~3문장 한국어로 답변하세요."
    messages = [{"role":"system","content":system}]
    for turn in history[-2:]:
        messages.append({"role":"user","content":turn["user"]})
        if persona["name"] in turn["responses"]:
            messages.append({"role":"assistant","content":turn["responses"][persona["name"]]})

    try:
        res = client.chat.completions.create(model=MODEL, messages=messages, temperature=0.7)
        return persona["name"], res.choices[0].message.content
    except Exception as e:
        return persona["name"], "⏳ 서버 정체 중.."

# --- UI 설정 ---
st.set_page_config(page_title="AI 커스텀 채팅", layout="centered")

# CSS로 스타일링
st.markdown("""
<style>
    .persona-card { text-align: center; border: 1px solid #ddd; border-radius: 10px; padding: 10px; background: #f9f9f9; }
    .persona-desc { font-size: 0.7rem; color: #666; margin-bottom: 5px; }
</style>
""", unsafe_allow_html=True)

st.title("⚡ AI 단체 채팅방")

# --- 1. 대화 상대 선택 및 설명 ---
st.subheader("👥 대화 상대 선택")
cols = st.columns(len(st.session_state.personas))
for i, p in enumerate(st.session_state.personas):
    with cols[i]:
        st.markdown(f"""
            <div class="persona-card">
                <div style="font-size:1.5rem;">{p['emoji']}</div>
                <div style="font-weight:bold; font-size:0.9rem;">{p['name']}</div>
                <div class="persona-desc">{p['desc']}</div>
            </div>
        """, unsafe_allow_html=True)
        if st.button("ON" if p["active"] else "OFF", key=f"p_{i}", type="primary" if p["active"] else "secondary", use_container_width=True):
            st.session_state.personas[i]["active"] = not p["active"]
            st.rerun()

st.divider()

# --- 2. 메인 화면에 캐릭터 추가 기능 ---
with st.expander("➕ 새로운 대화 상대 추가하기", expanded=False):
    c1, c2 = st.columns([1, 2])
    with c1:
        new_name = st.text_input("이름", placeholder="예: 철수")
        new_emoji = st.text_input("아이콘", value="👤")
    with c2:
        new_desc = st.text_input("짧은 설명", placeholder="예: 낙천적인 요리사")
        new_pers = st.text_area("상세 성격", placeholder="예: 항상 긍정적이며 요리 비유를 들어 말함.")
    
    if st.button("캐릭터 생성 및 참가", use_container_width=True):
        if new_name and new_pers:
            st.session_state.personas.append({
                "id": new_name.lower(), "name": new_name, "color": "#555", "emoji": new_emoji,
                "desc": new_desc, "personality": new_pers, "active": True
            })
            st.success(f"{new_name}이(가) 대화에 합류했습니다!")
            time.sleep(0.5)
            st.rerun()

st.divider()

# --- 3. 대화창 ---
for turn in st.session_state.history:
    with st.chat_message("user"): st.write(turn["user"])
    for p_name, ans in turn["responses"].items():
        p_data = next((x for x in st.session_state.personas if x["name"] == p_name), {"emoji":"👤"})
        with st.chat_message(p_name, avatar=p_data["emoji"]):
            st.write(f"**{p_name}**: {ans}")

# --- 4. 입력창 및 설정 ---
with st.sidebar:
    st.header("⚙️ 상세 설정")
    if st.button("🔄 전체 대화 초기화", use_container_width=True):
        st.session_state.history = []
        st.rerun()
    st.info("모델: llama-3.1-8b-instant (고속)")

if prompt := st.chat_input("메시지를 입력하세요..."):
    active_p = [p for p in st.session_state.personas if p["active"]]
    if active_p:
        st.session_state.history.append({"user": prompt, "responses": {}})
        with st.spinner("답변 생성 중..."):
            res_dict = {}
            for i, p in enumerate(active_p):
                name, text = ask_one(p, st.session_state.history, i)
                res_dict[name] = text
            st.session_state.history[-1]["responses"] = res_dict
        st.rerun()
