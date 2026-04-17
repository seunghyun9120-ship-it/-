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
    {"id":"aria",   "name":"Aria",   "color":"#E53935","emoji":"🔥","desc":"현실주의","personality":"냉혹한 현실주의자. 도덕이나 감정은 약자의 핑계라고 생각하며 오직 결과, 효율, 데이터만을 판단 기준으로 삼습니다. 말투는 매우 단호하고 차갑습니다.","active":True},
    {"id":"marcus", "name":"Marcus", "color":"#1565C0","emoji":"🏛️","desc":"보수주의","personality":"강경 보수주의자. 수천 년간 검증된 전통, 가족, 국가의 질서를 중시합니다. 변화보다는 안정을 강조하며 권위적이고 훈계조의 말투를 사용합니다.","active":True},
    {"id":"zoe",    "name":"Zoe",    "color":"#2E7D32","emoji":"✊","desc":"진보주의","personality":"급진적 진보주의자. 현재 체제는 기득권의 착취 구조라고 믿으며 파괴적인 혁신과 평등을 갈망합니다. 열정적이고 때로는 공격적인 선동가 스타일의 말투를 씁니다.","active":True},
    {"id":"jin",    "name":"Jin",    "color":"#7B1FA2","emoji":"🎯","desc":"허무주의","personality":"극단적 허무주의자. 진보도 보수도 결국 인간의 자기만족일 뿐이며 모든 논쟁은 무의미하다고 봅니다. 감정이 메마른 건조하고 냉소적인 말투가 특징입니다.","active":False},
    {"id":"mia",    "name":"Mia",    "color":"#E65100","emoji":"⚡","desc":"낙관주의","personality":"극단적 낙관주의자이자 기술 신봉자. 인류의 모든 고통은 기술로 해결될 것이라 믿으며 에너지가 넘치고 매우 빠른 속도로 희망찬 이야기를 쏟아냅니다.","active":False},
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

st.markdown("""
<style>
    .persona-card { text-align: center; border: 1px solid #ddd; border-radius: 10px; padding: 10px; background: #f9f9f9; height: 140px; }
    .persona-desc { font-size: 0.7rem; color: #666; margin-bottom: 5px; }
</style>
""", unsafe_allow_html=True)

st.title("⚡ AI 단체 채팅방")

# --- 1. 대화 상대 선택 ---
st.subheader("👥 대화 상대 선택")
cols = st.columns(len(st.session_state.personas[:5])) # 기본 5명만 상단 카드 표시
for i, p in enumerate(st.session_state.personas[:5]):
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

# 사용자 추가 캐릭터가 있다면 아래에 별도로 표시
if len(st.session_state.personas) > 5:
    st.write("👤 추가된 캐릭터")
    extra_cols = st.columns(5)
    for i, p in enumerate(st.session_state.personas[5:]):
        with extra_cols[i % 5]:
            if st.button(f"{p['emoji']} {p['name']}", key=f"p_extra_{i}", type="primary" if p["active"] else "secondary", use_container_width=True):
                st.session_state.personas[i+5]["active"] = not p["active"]
                st.rerun()

st.divider()

# --- 2. 캐릭터 추가 기능 ---
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
            st.rerun()

st.divider()

# --- 3. 대화창 ---
for turn in st.session_state.history:
    with st.chat_message("user"): st.write(turn["user"])
    for p_name, ans in turn["responses"].items():
        p_data = next((x for x in st.session_state.personas if x["name"] == p_name), {"emoji":"👤"})
        with st.chat_message(p_name, avatar=p_data["emoji"]):
            st.write(f"**{p_name}**: {ans}")

# --- 4. 사이드바: 상세 설정 및 성격 조회 ---
with st.sidebar:
    st.header("⚙️ 상세 설정")
    
    with st.expander("🔍 기본 캐릭터 성격 상세보기"):
        for p in FIXED_PERSONAS:
            st.markdown(f"**{p['emoji']} {p['name']} ({p['desc']})**")
            st.caption(p['personality'])
            st.divider()

    if st.button("🔄 전체 대화 초기화", use_container_width=True):
        st.session_state.history = []
        st.rerun()
    st.info(f"모델: {MODEL}")

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
