import os
import time
from html import escape
import re

import streamlit as st
from pydantic import ValidationError

from core import CRITERIA, DEFAULT_MODEL, MAX_JD, JDService, JobInput, UserError, quality_markdown

st.set_page_config(page_title="JD Studio | AI Job Description", page_icon="✦", layout="wide")
st.markdown("""<style>
.stApp {background: #f6f8fc;}
.block-container {max-width: 1240px; padding-top: 2.5rem;}
h1,h2,h3 {letter-spacing: -.025em;}
.hero {background: #142b40; border-radius: 20px; padding: 32px 36px; color: white; margin-bottom: 24px;}
.hero .eyebrow {color: #84dcc6; font-size: 12px; letter-spacing: .18em; font-weight: 700;}
.hero h1 {color: white; font-size: 40px; margin: 8px 0;}
.hero p {color: #dae4ee; font-size: 17px; margin: 4px 0;}
.result-text {white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.85; font-size: 16px;}
[data-testid="stMetric"] {background: white; border-radius: 12px; padding: 16px;}
</style>""", unsafe_allow_html=True)


def setting(name, fallback=""):
    env = os.environ.get(name)
    if env:
        return env.strip()
    try:
        return str(st.secrets.get(name, fallback)).strip()
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return fallback


def show_draft(text):
    # Render only headings, bullets and bold; links, images and raw HTML stay inert.
    blocks = []
    for line in text.splitlines():
        escaped = escape(line)
        escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
        if re.match(r"^#{1,6} ", line):
            blocks.append('<h4 dir="auto">' + re.sub(r"^#{1,6} ", "", escaped) + '</h4>')
        elif line.startswith(("- ", "* ")):
            blocks.append('<p dir="auto">• ' + escaped[2:] + '</p>')
        elif line.strip():
            blocks.append('<p dir="auto">' + escaped + '</p>')
    st.markdown('<div class="result-text">' + ''.join(blocks) + '</div>', unsafe_allow_html=True)


def safe_text(text):
    # All user/model text is escaped: no remote images, links or HTML execution.
    st.markdown(f'<div class="result-text" dir="auto">{escape(text)}</div>', unsafe_allow_html=True)


def run_action(action):
    if time.monotonic() - st.session_state.get("last_request", -100) < 3:
        st.warning("انتظر ثلاث ثوانٍ بين الطلبات / Please wait 3 seconds between requests.")
        return None
    st.session_state.last_request = time.monotonic()
    try:
        with st.spinner("نعمل على الوصف الوظيفي… / Working on your JD…"):
            service = JDService(setting("OPENAI_API_KEY"), setting("OPENAI_MODEL", DEFAULT_MODEL))
            return action(service)
    except UserError as exc:
        st.error(str(exc))
    except Exception:
        st.error("حدث خطأ غير متوقع. أعد المحاولة / Something went wrong; please retry.")
    return None


if "next_mode" in st.session_state:
    st.session_state["mode"] = st.session_state.pop("next_mode")

with st.sidebar:
    st.markdown("## ✦ JD Studio")
    st.caption("AI JOB DESCRIPTION GENERATOR & OPTIMIZER")
    st.divider()
    mode = st.radio("مساحة العمل / Workspace", ["إنشاء / Create", "تحسين / Improve", "تحليل / Analyze"], key="mode")
    language_label = st.selectbox("لغة الناتج / Output language", ["العربية", "English"])
    language = "Arabic" if language_label == "العربية" else "English"
    st.divider()
    configured = bool(setting("OPENAI_API_KEY"))
    if configured:
        st.success("الخدمة مهيأة / API configured")
    else:
        st.info("أضف المفتاح في Secrets لتفعيل الذكاء الاصطناعي.")
    st.caption("تُرسل المدخلات إلى OpenAI عند تنفيذ الطلب. لا يحفظ التطبيق الأوصاف في قاعدة بيانات؛ تبقى نتائجك في الجلسة الحالية فقط.")
    if st.button("مسح الجلسة / Clear session", use_container_width=True):
        for key in list(st.session_state):
            if key not in ("mode",):
                del st.session_state[key]
        st.rerun()

st.markdown("""<div class="hero"><div class="eyebrow">PURPOSE → CLARITY → BETTER JOB DESCRIPTIONS</div>
<h1>Better roles. Clearly written.</h1><p dir="rtl">وصف وظيفي واضح. توقعات أدق. بداية أفضل للتوظيف.</p>
<p>Create, refine and review professional job descriptions.</p></div>""", unsafe_allow_html=True)

if not configured:
    st.info("التطبيق جاهز للإعداد. أضف OPENAI_API_KEY في Streamlit Secrets؛ لا تضعه في الكود أو الدردشة. يمكنك استعراض الواجهة وإدخال البيانات الآن.")

SAMPLE = """نبحث عن أخصائي موارد بشرية للعمل بدوام كامل في الرياض في شركة خدمات مهنية.
يتولى متابعة ملفات الموظفين، تنسيق التوظيف، إعداد تقارير الموارد البشرية، ومتابعة الحضور والإجازات.
المطلوب إجادة Excel ومهارات تواصل وتنظيم جيدة وخبرة في عمليات الموارد البشرية.
"""

if mode == "إنشاء / Create":
    st.subheader("01 / ابدأ بتفاصيل الدور")
    st.caption("أدخل المعلومات المؤكدة. ستظهر الإضافات المقترحة بوضوح لمراجعتها قبل الاعتماد.")
    with st.form("generate_form"):
        a, b = st.columns(2)
        title = a.text_input("المسمى الوظيفي / Job title *", max_chars=120, placeholder="أخصائي موارد بشرية")
        department = b.text_input("الإدارة / Department *", max_chars=120, placeholder="الموارد البشرية")
        seniority = a.selectbox("المستوى / Seniority", ["مبتدئ / Entry", "متوسط / Mid-level", "خبير / Senior", "إداري / Manager", "قيادي / Director"])
        industry = b.text_input("القطاع / Industry *", max_chars=120, placeholder="الخدمات المهنية")
        location = a.text_input("الموقع / Location", max_chars=160, placeholder="الرياض، السعودية")
        work_type = b.selectbox("نمط العمل / Work arrangement", ["غير محدد / Not specified", "حضوري / On-site", "هجين / Hybrid", "عن بُعد / Remote"])
        requirements = st.text_area("المهام والمتطلبات الأساسية / Key responsibilities & requirements *", max_chars=4000, height=130,
                                    placeholder="المهام الأساسية، المهارات الضرورية، وأي معلومات مؤكدة عن الدور…")
        submitted = st.form_submit_button("✦ إنشاء الوصف / Generate JD", type="primary", disabled=not configured)
    if submitted:
        try:
            job = JobInput(title=title.strip(), department=department.strip(), seniority=seniority,
                           industry=industry.strip(), location=location.strip(), work_type=work_type,
                           requirements=requirements.strip(), language=language)
            draft = run_action(lambda service: service.generate(job))
            if draft:
                st.session_state["create_result"] = {"draft": draft, "quality": None, "language": language}
        except ValidationError:
            st.error("أكمل الحقول الإلزامية: حرفان على الأقل للمسمى والإدارة والقطاع، و10 أحرف للمتطلبات.")
    result_key = "create_result"
else:
    improving = mode == "تحسين / Improve"
    prefix = "improve" if improving else "analyze"
    st.subheader("02 / حسّن وصفًا موجودًا" if improving else "03 / افهم جودة الوصف")
    if st.button("تحميل مثال / Load sample", key=prefix + "_sample"):
        st.session_state[prefix + "_source"] = SAMPLE
    with st.form(prefix + "_form"):
        source = st.text_area("الوصف الوظيفي الحالي / Existing job description", height=260,
                              max_chars=MAX_JD, key=prefix + "_source")
        st.caption("80–16,000 حرف. احذف أي معلومات سرية قبل الإرسال.")
        submitted = st.form_submit_button("✦ تحسين الوصف / Improve JD" if improving else "✦ تحليل الجودة / Analyze quality",
                                          type="primary", disabled=not configured)
    if submitted:
        from core import validate_jd
        try:
            clean = validate_jd(source)
            output = run_action(lambda service: service.improve(clean, language) if improving else service.analyze(clean, language))
            if output:
                st.session_state[prefix + "_result"] = {
                    "draft": output if improving else None, "quality": None if improving else output,
                    "source": clean, "language": language,
                }
        except UserError as exc:
            st.error(str(exc))
    result_key = prefix + "_result"

result = st.session_state.get(result_key)
if result:
    st.divider()
    st.caption("نتيجة آخر طلب ناجح في هذا الوضع؛ تعديل الحقول لا يغيرها حتى تنفيذ طلب جديد.")
    draft = result.get("draft")
    if draft:
        st.subheader("الوصف المقترح / Your draft")
        with st.container(border=True):
            show_draft(draft.jd)
        with st.expander("ملاحظات وتغييرات / Notes & changes", expanded=True):
            for note in draft.notes:
                safe_text("• " + note)
        if "source" in result:
            with st.expander("الوصف الأصلي / Original JD"):
                safe_text(result["source"])
        c1, c2 = st.columns(2)
        c1.download_button("↓ تنزيل TXT", draft.jd.encode("utf-8-sig"), "job-description.txt", "text/plain", key=result_key + "txt")
        c2.download_button("↓ تنزيل Markdown", draft.jd, "job-description.md", "text/markdown", key=result_key + "md")
        with st.expander("نسخ النص / Copy text"):
            st.caption("استخدم زر النسخ أعلى مربع النص / Use the copy icon in the top-right corner.")
            st.code(draft.jd, language=None, wrap_lines=True)
        if st.button("تحليل جودة هذه النسخة / Analyze this draft", key=result_key + "score", disabled=not configured):
            quality = run_action(lambda service: service.analyze(draft.jd, result["language"]))
            if quality:
                result["quality"] = quality
    quality = result.get("quality")
    if quality:
        st.subheader("تقرير الجودة / Quality report")
        st.metric("Quality score", f"{quality.total}/100")
        st.progress(quality.total / 100)
        safe_text(quality.summary)
        st.caption("تقدير تحريري بالذكاء الاصطناعي، وليس مقياسًا معتمدًا أو ضمانًا قانونيًا. قد تتغير الدرجة بين المحاولات.")
        for key, (label, weight) in CRITERIA.items():
            item = getattr(quality, key)
            with st.expander(f"{label} · {item.score}/10 · الوزن {weight}%"):
                st.caption("الدليل / Evidence")
                safe_text(item.evidence)
                st.caption("التحسين المقترح / Recommendation")
                safe_text(item.recommendation)
        with st.expander("كيف تُحسب الدرجة؟ / Scoring method"):
            st.write("مجموع (درجة المعيار من 10 × وزنه) ÷ 10، مقربًا لأقرب عدد صحيح. صفر = غائب؛ 1–3 = ضعيف؛ 4–6 = جزئي؛ 7–8 = واضح؛ 9–10 = مكتمل ومحدد للدور.")
        st.download_button("↓ تنزيل تقرير الجودة", quality_markdown(quality), "quality-report.md", "text/markdown", key=result_key + "report")
        if not draft:
            with st.expander("النص الذي تم تحليله / Analyzed source"):
                safe_text(result["source"])
            if st.button("تحسين هذا الوصف / Improve this JD"):
                st.session_state["improve_source"] = result["source"]
                st.session_state["next_mode"] = "تحسين / Improve"
                st.rerun()
else:
    st.markdown("---")
    st.caption("✦ ستظهر النتيجة هنا بعد تنفيذ الطلب / Your result will appear here.")

st.divider()
st.caption("JD Studio · Diploma MVP · راجع المسودة والمقترحات قبل نشرها أو اعتمادها.")
