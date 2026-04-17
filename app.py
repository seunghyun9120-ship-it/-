import streamlit as st
import os, json, datetime, re
from openai import OpenAI
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor

# 라이브러리 체크 및 로드 (최신 버전 대응)
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

# --- API KEY 로드 (Streamlit Cloud Secrets 대응) ---
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

# --- 세션 초기화 ---
if "personas" not in st.session_state:
    st.session_state.personas = [dict(p) for p in FIXED_PERSONAS]
if "history" not in st.session_state: st.session_state.history = []
if "input_key" not in st.session_state: st.session_state.input_key = 0
if "debate_mode" not in st.session_state: st.session_state.debate_mode = False
if "fact_filter_on" not in st.session_state: st.session_state.fact_filter_on = True

# --- 웹 검색 (최신 DDGS 대응) ---
def web_search(query):
    if not DDG_AVAILABLE: return ""
    try:
        with DDGS() as ddgs:
            # 최신 라이브러리 문법으로 수정
            results = [r for r in ddgs.text(query, max_results=5)]
            if not results: return ""
            return "\n".join([f"[{r.get('published', '')[:10]}] {r.get('body', '')}" for r in results])
    except: return ""

def wikipedia_search(query):
    if not REQUESTS_AVAILABLE: return ""
    try:
        r = req.get(f"https://ko.wikipedia.org/api/rest_v1/page/summary/{req.utils.quote(query)}", timeout=5).json()
        if "extract" in r: return f"[Wikipedia] {r.get('title','')}: {r['extract'][:500]}"
    except: pass
    return ""

def collect_all_data(query):
    today = f"오늘 날짜: {datetime.datetime.now().strftime('%Y년 %m월 %d일')}"
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_web = ex.submit(web_search, query)
        f_wiki = ex.submit(wikipedia_search, query)
        web, wiki = f_web.result(), f_wiki.result()
    
    parts = [today]
    if wiki: parts.append(wiki)
    if web:  parts.append(web)
    return "\n\n".join(parts)

# --- AI 응답 로직 ---
def ask_one(persona, history, web_data="", debate_ctx=""):
    system = (f"당신은 {persona['name']}입니다. {persona['personality']}\n"
              f"3~4문장 한국어 구어체로만 답변하세요. 영어 사용 금지.\n"
              f"제공된 데이터가 있다면 그 내용을 바탕으로 당신의 성향에 맞춰 답변하세요.\n"
              f"[참고 데이터]\n{web_data}\n"
              f"[토론 문맥]\n{debate_ctx}")
    
    messages = [{"role":"system","content":system}]
    for turn in history[-3:]:
        messages.append({"role":"user","content":turn["user"]})
        if persona["name"] in turn["responses"]:
            messages.append({"role":"assistant","content":turn["responses"][persona["name"]]})

    try:
        res = client.chat.completions.create(model=MODEL, messages=messages, temperature=0.8)
        return persona["name"], res.choices[0].message.content
    except Exception as e:
        return persona["name"], f"응답 오류: {str(e)[:50]}"

def run_chat(history, question):
    web_data = collect_all_data(question)
    active = [p for p in st.session_state.personas if p["active"]]
    
    with ThreadPoolExecutor(max_workers=len(active)) as ex:
        futures = [ex.submit(ask_one, p, history, web_data, "") for p in active]
        responses = dict([f.result() for f in futures])
    
    return responses

# --- UI (간소화 및 최적화) ---
st.set_page_config(page_title="AI 대화방", layout="centered")

with st.sidebar:
    st.header("⚙️ 설정")
    st.session_state.debate_mode = st.toggle("⚔️ 토론 모드", st.session_state.debate_mode)
    if st.button("🔄 대화 초기화"):
        st.session_state.history = []
        st.rerun()

st.title("💬 AI 단체 채팅")

# 캐릭터 선택 UI
cols = st.columns(len(st.session_state.personas))
for i, p in enumerate(st.session_state.personas):
    with cols[i]:
        st.markdown(f"### {p['emoji']}")
        if st.button(p["name"], type="primary" if p["active"] else "secondary", key=f"btn_{i}"):
            st.session_state.personas[i]["active"] = not p["active"]
            st.rerun()

st.divider()

# 대화 내용 출력
for turn in st.session_state.history:
    with st.chat_message("user"):
        st.write(turn["user"])
    for p_name, ans in turn["responses"].items():
        p_data = next(x for x in st.session_state.personas if x["name"] == p_name)
        with st.chat_message(p_name, avatar=p_data["emoji"]):
            st.markdown(f"**{p_name}**: {ans}")

# 입력창
if prompt := st.chat_input("메시지를 입력하세요..."):
    if not any(p["active"] for p in st.session_state.personas):
        st.warning("대화 상대를 한 명 이상 선택해주세요.")
    else:
        st.session_state.history.append({"user": prompt, "responses": {}})
        with st.spinner("AI가 생각 중입니다..."):
            res = run_chat(st.session_state.history, prompt)
            st.session_state.history[-1]["responses"] = res
        st.rerun()
