import streamlit as st
import os, json, datetime, re, time
from openai import OpenAI
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor

# 라이브러리 체크
try:
    from duckduckgo_search import DDGS
    DDG_AVAILABLE = True
except ImportError:
    DDG_AVAILABLE = False

try:
    import requests as req
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

load_dotenv()

# --- API KEY 설정 (Streamlit Secrets 우선) ---
if "GROQ_API_KEY" in st.secrets:
    api_key = st.secrets["GROQ_API_KEY"]
else:
    api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    st.error("❌ API 키를 찾을 수 없습니다. Secrets 설정을 확인하세요.")
    st.stop()

client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key)
MODEL = "llama-3.3-70b-versatile"

# --- 페르소나 설정 ---
FIXED_PERSONAS = [
    {"id":"aria",   "name":"Aria",   "color":"#E53935","emoji":"🔥","desc":"냉혹한 현실주의자","personality":"냉혹한 현실주의자. 도덕이나 감정은 약자의 핑계. 오직 결과와 효율만 판단 기준. 말투는 짧고 단호하며 칼같음.","fixed":True,"active":True},
    {"id":"marcus", "name":"Marcus", "color":"#1565C0","emoji":"🏛️","desc":"강경 보수주의자",  "personality":"강경 보수주의자. 수천 년 검증된 전통·가족·국가가 사회의 근간. 개인주의와 다양성 강조가 사회 붕괴를 불러온다고 확신. 말투는 권위적이고 단정적.","fixed":True,"active":True},
    {"id":"zoe",    "name":"Zoe",    "color":"#2E7D32","emoji":"✊","desc":"급진적 진보주의자","personality":"급진적 진보주의자. 현재 체제는 기득권의 착취 구조. 개혁이 아닌 혁명이 필요하다고 확신. 말투는 열정적이고 공격적.","fixed":True,"active":True},
    {"id":"jin",    "name":"Jin",    "color":"#7B1FA2","emoji":"🎯","desc":"극단적 허무주의자","personality":"극단적 허무주의자. 어떤 주장도 결국 의미 없음. 진보도 보수도 다 자기 위안. 말투는 건조하고 냉소적.","fixed":True,"active":True},
    {"id":"mia",    "name":"Mia",    "color":"#E65100","emoji":"⚡","desc":"극단적 낙관주의자","personality":"극단적 낙관주의자이자 기술 신봉자. AI와 기술이 모든 문제를 해결한다고 믿음. 말투는 에너지 넘치고 빠름.","fixed":True,"active":True},
]

# --- 세션 관리 ---
if "personas" not in st.session_state:
    st.session_state.personas = [dict(p) for p in FIXED_PERSONAS]
if "history" not in st.session_state: st.session_state.history = []
if "input_key" not in st.session_state: st.session_state.input_key = 0

# --- 데이터 엔진 ---
def web_search(query):
    if not DDG_AVAILABLE: return ""
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=5)]
            return "\n".join([f"[{r.get('body', '')[:200]}]" for r in results])
    except: return ""

def wikipedia_search(query):
    if not REQUESTS_AVAILABLE: return ""
    try:
        r = req.get(f"https://ko.wikipedia.org/api/rest_v1/page/summary/{req.utils.quote(query)}", timeout=5).json()
        return f"Wiki: {r.get('extract','')[:300]}" if "extract" in r else ""
    except: return ""

# --- 핵심: AI 응답 (순차적 요청으로 429 방지) ---
def ask_one(persona, history, web_data="", idx=0):
    # 각 요청 사이에 짧은 간격을 두어 Rate Limit 회피
    time.sleep(idx * 0.6) 
    
    system = (f"당신은 {persona['name']}입니다. {persona['personality']}\n"
              f"3~4문장 한국어 구어체로만. 영어 금지. 제공된 데이터를 성향껏 해석하세요.\n"
              f"[참고 데이터] {web_data}")
    
    messages = [{"role":"system","content":system}]
    for turn in history[-3:]:
        messages.append({"role":"user","content":turn["user"]})
        if persona["name"] in turn["responses"]:
            messages.append({"role":"assistant","content":turn["responses"][persona["name"]]})

    try:
        res = client.chat.completions.create(model=MODEL, messages=messages, temperature=0.8)
        return persona["name"], res.choices[0].message.content
    except Exception as e:
        if "429" in str(e): return persona["name"], "⏳ (서버 과부하로 잠시 쉬는 중입니다. 잠시 후 다시 시도해주세요.)"
        return persona["name"], f"오류 발생: {str(e)[:30]}"

# --- UI 설정 ---
st.set_page_config(page_title="AI 토론장", layout="centered")
st.markdown("""
<style>
    .stApp { background: #fff; }
    .ai-name { font-size:0.75rem; font-weight:700; margin-top:10px; }
    .bubble-ai { background:#F1F3F5; border-radius:4px 15px 15px 15px; padding:10px 15px; font-size:0.92rem; line-height:1.6; }
    .card-desc { font-size:0.6rem; color:#888; margin-top:2px; }
</style>
""", unsafe_allow_html=True)

# 사이드바
with st.sidebar:
    st.header("⚙️ 설정")
    if st.button("🔄 대화 내용 초기화", use_container_width=True):
        st.session_state.history = []; st.rerun()

st.title("💬 AI 단체 채팅")

# 캐릭터 선택 카드
st.markdown('<p style="font-size:0.8rem; font-weight:700; color:#888;">대화 상대 선택</p>', unsafe_allow_html=True)
cols = st.columns(len(st.session_state.personas))
for i, p in enumerate(st.session_state.personas):
    with cols[i]:
        is_on = p["active"]
        st.markdown(f"""
            <div style="background:{'#EBF5FF' if is_on else '#F8F9FA'}; border:2px solid {p['color'] if is_on else '#EEE'}; 
                        border-radius:12px; padding:8px 4px; text-align:center;">
                <div style="font-size:1.2rem;">{p['emoji']}</div>
                <div style="font-size:0.75rem; font-weight:700; color:{p['color'] if is_on else '#555'};">{p['name']}</div>
                <div class="card-desc">{p['desc']}</div>
            </div>
        """, unsafe_allow_html=True)
        if st.button("ON" if is_on else "OFF", key=f"t_{i}", use_container_width=True, type="primary" if is_on else "secondary"):
            st.session_state.personas[i]["active"] = not is_on; st.rerun()

st.divider()

# 대화창
for turn in st.session_state.history:
    with st.chat_message("user"): st.write(turn["user"])
    for p_name, ans in turn["responses"].items():
        p_data = next(x for x in st.session_state.personas if x["name"] == p_name)
        st.markdown(f'<div class="ai-name" style="color:{p_data["color"]}">{p_data["emoji"]} {p_name}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="bubble-ai">{ans}</div>', unsafe_allow_html=True)

# 입력
if prompt := st.chat_input("메시지를 입력하세요..."):
    active_p = [p for p in st.session_state.personas if p["active"]]
    if not active_p:
        st.warning("상대를 선택해주세요.")
    else:
        st.session_state.history.append({"user": prompt, "responses": {}})
        with st.spinner("데이터 분석 및 답변 생성 중..."):
            web_data = web_search(prompt) + wikipedia_search(prompt)
            # 순차적 처리 (Rate Limit 방어 핵심)
            res_dict = {}
            for i, p in enumerate(active_p):
                name, text = ask_one(p, st.session_state.history, web_data, i)
                res_dict[name] = text
            st.session_state.history[-1]["responses"] = res_dict
        st.rerun()
