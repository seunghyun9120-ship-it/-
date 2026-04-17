import streamlit as st
import os, json, datetime, re
from openai import OpenAI
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor

# 라이브러리 체크 및 로드
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

try:
    import praw
    REDDIT_AVAILABLE = True
except ImportError:
    REDDIT_AVAILABLE = False

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    st.error("❌ GROQ_API_KEY가 .env 파일에 없습니다.")
    st.stop()

client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key)
MODEL = "llama-3.3-70b-versatile"

# --- 페르소나 초기 설정 ---
FIXED_PERSONAS = [
    {"id":"aria",   "name":"Aria",   "color":"#E53935","emoji":"🔥","desc":"냉혹한 현실주의자","personality":"냉혹한 현실주의자. 도덕이나 감정은 약자의 핑계. 오직 결과와 효율만 판단 기준. 말투는 짧고 단호하며 칼같음.","fixed":True,"active":True},
    {"id":"marcus", "name":"Marcus", "color":"#1565C0","emoji":"🏛️","desc":"강경 보수주의자",  "personality":"강경 보수주의자. 수천 년 검증된 전통·가족·국가가 사회의 근간. 개인주의와 다양성 강조가 사회 붕괴를 불러온다고 확신. 말투는 권위적이고 단정적.","fixed":True,"active":True},
    {"id":"zoe",    "name":"Zoe",    "color":"#2E7D32","emoji":"✊","desc":"급진적 진보주의자","personality":"급진적 진보주의자. 현재 체제는 기득권의 착취 구조. 개혁이 아닌 혁명이 필요하다고 확신. 말투는 열정적이고 공격적.","fixed":True,"active":True},
    {"id":"jin",    "name":"Jin",    "color":"#7B1FA2","emoji":"🎯","desc":"극단적 허무주의자","personality":"극단적 허무주의자. 어떤 주장도 결국 의미 없음. 진보도 보수도 다 자기 위안. 말투는 건조하고 냉소적.","fixed":True,"active":True},
    {"id":"mia",    "name":"Mia",    "color":"#E65100","emoji":"⚡","desc":"극단적 낙관주의자","personality":"극단적 낙관주의자이자 기술 신봉자. AI와 기술이 모든 문제를 해결한다고 믿음. 말투는 에너지 넘치고 빠름.","fixed":True,"active":True},
]
CUSTOM_COLORS = ["#00838F","#AD1457","#558B2F","#4527A0","#BF360C","#00695C"]
CUSTOM_EMOJIS = ["😎","🦊","🐺","🦁","🐉","👁️"]

def init_session():
    if "personas" not in st.session_state:
        st.session_state.personas = [dict(p) for p in FIXED_PERSONAS]
    if "history" not in st.session_state: st.session_state.history = []
    if "input_key" not in st.session_state: st.session_state.input_key = 0
    if "debate_mode" not in st.session_state: st.session_state.debate_mode = False
    if "fact_filter_on" not in st.session_state: st.session_state.fact_filter_on = True
    if "show_add" not in st.session_state: st.session_state.show_add = False

init_session()

# --- 데이터 수집 엔진 ---
def search_youtube_videos(query, max_results=3):
    yt_key = os.getenv("YOUTUBE_API_KEY")
    if not yt_key or not REQUESTS_AVAILABLE: return []
    try:
        r = req.get("https://www.googleapis.com/youtube/v3/search", params={
            "part":"snippet","q":query+" 뉴스","type":"video",
            "maxResults":max_results,"order":"relevance","relevanceLanguage":"ko","key":yt_key
        }, timeout=10).json()
        return [i["id"]["videoId"] for i in r.get("items",[]) if "videoId" in i.get("id",{})]
    except: return []

def fetch_comments_by_id(vid, n=20):
    yt_key = os.getenv("YOUTUBE_API_KEY")
    if not yt_key: return []
    try:
        cr = req.get("https://www.googleapis.com/youtube/v3/commentThreads", params={
            "part":"snippet","videoId":vid,"maxResults":n,"order":"relevance","key":yt_key
        }, timeout=10).json()
        return [i["snippet"]["topLevelComment"]["snippet"]["textDisplay"] for i in cr.get("items",[])]
    except: return []

def auto_fetch_youtube_context(query):
    if not os.getenv("YOUTUBE_API_KEY") or not REQUESTS_AVAILABLE: return ""
    vids = search_youtube_videos(query, 2)
    comments = []
    for v in vids: comments.extend(fetch_comments_by_id(v, 15))
    return "\n".join([f"- {c}" for c in comments[:30]])

def web_search(query):
    if not DDG_AVAILABLE: return ""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5, timelimit="m"))
            if not results: results = list(ddgs.text(query, max_results=5))
            return "\n".join([f"[{r.get('published', '')[:10]}] {r['body']}" for r in results])
    except: return ""

def wikipedia_search(query):
    if not REQUESTS_AVAILABLE: return ""
    try:
        # KO 우선 -> EN 폴백
        for lang in ["ko", "en"]:
            r = req.get(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{req.utils.quote(query)}", timeout=5).json()
            if "extract" in r: return f"[Wikipedia {lang.upper()}] {r.get('title','')}: {r['extract'][:500]}"
    except: pass
    return ""

def reddit_search(query):
    rid, rsec = os.getenv("REDDIT_CLIENT_ID"), os.getenv("REDDIT_CLIENT_SECRET")
    if not (rid and rsec and REDDIT_AVAILABLE): return ""
    try:
        reddit = praw.Reddit(client_id=rid, client_secret=rsec, user_agent="chatapp/1.0")
        posts = [f"[Reddit/{p.subreddit}] {p.title}: {p.selftext[:150]}" for p in reddit.subreddit("all").search(query, limit=5, time_filter="month")]
        return "\n".join(posts)
    except: return ""

def collect_all_data(query):
    today = f"오늘 날짜: {datetime.datetime.now().strftime('%Y년 %m월 %d일')}"
    with ThreadPoolExecutor(max_workers=4) as ex:
        f_web = ex.submit(web_search, query); f_wiki = ex.submit(wikipedia_search, query)
        f_yt = ex.submit(auto_fetch_youtube_context, query); f_rd = ex.submit(reddit_search, query)
        web, wiki, yt, rd = f_web.result(), f_wiki.result(), f_yt.result(), f_rd.result()
    
    parts = [today]
    if wiki: parts.append(f"[Wikipedia 팩트]\n{wiki}")
    if web:  parts.append(f"[실시간 웹 검색]\n{web}")
    if rd:   parts.append(f"[Reddit 여론]\n{rd}")
    return "\n\n".join(parts), yt

# --- 로직 엔진 ---
def fact_filter(responses: dict, raw_data: str, question: str) -> dict:
    if not responses or not raw_data: return responses
    answers_text = "\n\n".join([f"[{n}]: {responses[n]}" for n in responses])
    prompt = f"질문: {question}\n\n[실제 데이터]\n{raw_data[:2000]}\n\n[답변들]\n{answers_text}\n\n위 답변 중 사실 오류만 수정하여 JSON {{'filtered': {{'이름': '수정본'}}}} 형식으로 반환해."
    try:
        resp = client.chat.completions.create(model=MODEL, messages=[{"role":"system","content":"팩트체커. 사실만 교정. JSON만."}, {"role":"user","content":prompt}])
        m = re.search(r'\{.*\}', resp.choices[0].message.content, re.DOTALL)
        if m:
            filtered = json.loads(m.group()).get("filtered", {})
            return {k: filtered.get(k, v) for k, v in responses.items()}
    except: pass
    return responses

def ask_one(persona, history, web_data="", debate_ctx="", yt_comments=""):
    system = f"이름: {persona['name']}\n성격: {persona['personality']}\n지침: 3-4문장 한국어 구어체. 데이터 근거 필수. 영어 금지.\n\n[데이터]\n{web_data}\n\n[유튜브]\n{yt_comments}\n\n[토론 문맥]\n{debate_ctx}"
    messages = [{"role":"system","content":system}]
    for turn in history[-3:]:
        messages.append({"role":"user","content":turn["user"]})
        if persona["name"] in turn["responses"]:
            messages.append({"role":"assistant","content":turn["responses"][persona["name"]]})
    try:
        res = client.chat.completions.create(model=MODEL, messages=messages, temperature=0.9)
        return persona["name"], res.choices[0].message.content
    except: return persona["name"], "응답을 생성할 수 없습니다."

def run_chat(history, question):
    web_data, yt_comments = collect_all_data(question)
    active = [p for p in st.session_state.personas if p["active"]]
    
    with ThreadPoolExecutor(max_workers=5) as ex:
        first = dict([ex.submit(ask_one, p, history, web_data, "", yt_comments).result() for p in active])
    
    if st.session_state.debate_mode:
        ctx = "\n".join([f"{n}: {a}" for n, a in first.items()])
        with ThreadPoolExecutor(max_workers=5) as ex:
            second = dict([ex.submit(ask_one, p, history, web_data, ctx, yt_comments).result() for p in active])
        responses = {k: f"{first[k]}\n\n↩️ {second[k]}" for k in first}
    else:
        responses = first

    if st.session_state.fact_filter_on:
        responses = fact_filter(responses, web_data, question)
    return responses

# --- UI 레이아웃 ---
st.set_page_config(page_title="AI 단체 채팅", layout="centered")
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');
    * { font-family: 'Noto Sans KR', sans-serif; }
    .section-title { font-size:0.8rem; font-weight:700; color:#888; margin-bottom:12px; letter-spacing:0.05em; }
    .bubble-me { background:#4F86F7; color:white; border-radius:18px 4px 18px 18px; padding:10px 15px; max-width:70%; margin-left:auto; font-size:0.92rem; }
    .bubble-ai { background:#F3F4F6; color:#111; border-radius:4px 18px 18px 18px; padding:10px 15px; font-size:0.92rem; line-height:1.6; }
    .ai-name { font-size:0.75rem; font-weight:700; margin-bottom:4px; margin-top:12px; }
    .card-desc { font-size:0.62rem; color:#999; margin-top:2px; line-height:1.2; }
    .stButton > button { border-radius:12px !important; }
</style>
""", unsafe_allow_html=True)

# 사이드바 설정
with st.sidebar:
    st.header("⚙️ 설정")
    st.session_state.debate_mode = st.toggle("⚔️ 토론 모드", value=st.session_state.debate_mode)
    st.session_state.fact_filter_on = st.toggle("✅ 팩트 필터링", value=st.session_state.fact_filter_on)
    
    st.divider()
    st.markdown("**🎭 상세 성향 설정**")
    for i, p in enumerate(st.session_state.personas):
        with st.expander(f"{p['emoji']} {p['name']}"):
            st.session_state.personas[i]["personality"] = st.text_area("성격 정의", value=p["personality"], key=f"p_{i}", height=100)
            if not p.get("fixed", False):
                if st.button("🗑️ 삭제", key=f"del_{i}"):
                    st.session_state.personas.pop(i); st.rerun()

    if st.button("🔄 대화 초기화", use_container_width=True):
        st.session_state.history = []; st.session_state.input_key += 1; st.rerun()

st.title("💬 AI 단체 채팅")

# 캐릭터 선택 카드 (이름 아래 설명 포함)
st.markdown('<div class="section-title">대화 상대 선택</div>', unsafe_allow_html=True)
cols = st.columns(len(st.session_state.personas) + 1)

for i, p in enumerate(st.session_state.personas):
    with cols[i]:
        is_on = p["active"]
        bg = "#EFF6FF" if is_on else "#FAFAFA"
        border = p["color"] + "88" if is_on else "#EEE"
        # UI: 아이콘 + 이름 + 설명(desc)
        st.markdown(f"""
            <div style="background:{bg}; border:2px solid {border}; border-radius:14px; padding:10px 4px 8px; text-align:center; min-height:100px;">
                <div style="font-size:1.4rem;">{p['emoji']}</div>
                <div style="font-size:0.8rem; font-weight:700; color:{p['color'] if is_on else '#555'};">{p['name']}</div>
                <div class="card-desc">{p.get('desc', '')[:12]}</div>
            </div>
        """, unsafe_allow_html=True)
        if st.button("ON" if is_on else "OFF", key=f"btn_{i}", use_container_width=True, type="primary" if is_on else "secondary"):
            st.session_state.personas[i]["active"] = not is_on
            st.rerun()

# 캐릭터 추가 버튼
with cols[-1]:
    st.markdown("""<div style="border:2px dashed #DDD; border-radius:14px; padding:10px 4px 8px; text-align:center; min-height:100px; color:#AAA;"><div style="font-size:1.4rem;">＋</div><div style="font-size:0.8rem;">추가</div></div>""", unsafe_allow_html=True)
    if st.button("＋", key="add_btn", use_container_width=True):
        st.session_state.show_add = not st.session_state.show_add
        st.rerun()

if st.session_state.show_add:
    with st.container(border=True):
        c1, c2 = st.columns(2)
        new_n = c1.text_input("이름")
        new_d = c2.text_input("짧은 설명 (예: 냉소적)")
        new_p = st.text_area("상세 성향")
        if st.button("생성 완료", type="primary"):
            if new_n and new_p:
                st.session_state.personas.append({"id":new_n, "name":new_n, "emoji":"👤", "color":"#555", "desc":new_d, "personality":new_p, "active":True, "fixed":False})
                st.session_state.show_add = False; st.rerun()

st.divider()

# 대화창 출력
for turn in st.session_state.history:
    st.markdown(f'<div class="msg-me"><div class="bubble-me">{turn["user"]}</div></div>', unsafe_allow_html=True)
    for p_name, ans in turn["responses"].items():
        p_data = next((x for x in st.session_state.personas if x["name"] == p_name), {"color":"#555","emoji":"👤"})
        st.markdown(f'<div class="ai-name" style="color:{p_data["color"]}">{p_data["emoji"]} {p_name}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="bubble-ai">{ans}</div>', unsafe_allow_html=True)
    st.markdown('<div style="margin:20px 0; border-top:1px solid #F0F0F0;"></div>', unsafe_allow_html=True)

# 입력창
with st.form(key=f"input_{st.session_state.input_key}", clear_on_submit=True):
    c1, c2 = st.columns([5, 1])
    u_in = c1.text_input("메시지", label_visibility="collapsed", placeholder="내용을 입력하세요...")
    send = c2.form_submit_button("전송", use_container_width=True, type="primary")

if send and u_in.strip():
    if not any(p["active"] for p in st.session_state.personas):
        st.warning("상대를 선택해주세요."); st.stop()
    
    st.session_state.history.append({"user": u_in, "responses": {}})
    with st.spinner("정보를 수집하고 답변을 생성하는 중..."):
        res = run_chat(st.session_state.history, u_in)
        st.session_state.history[-1]["responses"] = res
    st.session_state.input_key += 1; st.rerun()