"""키워드 뉴스레터 자동 수집·발송 — Streamlit 메인 앱."""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from config import (
    NEWS_HOURS_LOOKBACK,
    NEWS_MAX_PER_KEYWORD,
    SCHEDULE_HOUR,
    SCHEDULE_MINUTE,
    SCHEDULE_TIMEZONE,
    credential_status,
)
from mailer import build_newsletter_content, send_newsletter
from news_api import collect_all_news
from scheduler import get_next_run_time, is_scheduler_running, start_daily_scheduler
from storage import (
    add_keyword,
    add_recipient,
    load_settings,
    remove_keyword,
    remove_recipient,
    save_settings,
)
from utils import logger

# ── 페이지 설정 ──────────────────────────────────────────────
st.set_page_config(
    page_title="Keyword Newsletter",
    page_icon="📬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 토스/노션 스타일 커스텀 CSS ──────────────────────────────
st.markdown(
    """
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

html, body, [class*="css"] {
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif;
}
.block-container { padding-top: 2rem; max-width: 1100px; }
section[data-testid="stSidebar"] {
    background: #fafafa;
    border-right: 1px solid #e4e4e7;
}
section[data-testid="stSidebar"] .block-container { padding-top: 1.5rem; }

.stat-card {
    background: #fff;
    border: 1px solid #e4e4e7;
    border-radius: 12px;
    padding: 20px 24px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
.stat-label { font-size: 13px; color: #71717a; margin-bottom: 4px; }
.stat-value { font-size: 28px; font-weight: 700; color: #18181b; letter-spacing: -0.02em; }
.stat-sub { font-size: 12px; color: #a1a1aa; margin-top: 4px; }

.tag-chip {
    display: inline-block;
    background: #f4f4f5;
    border: 1px solid #e4e4e7;
    border-radius: 20px;
    padding: 4px 12px;
    margin: 0 6px 6px 0;
    font-size: 13px;
    color: #3f3f46;
}
.status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
.status-on { background: #22c55e; }
.status-off { background: #ef4444; }

div.stButton > button[kind="primary"] {
    background: #3182f6;
    border: none;
    border-radius: 10px;
    font-weight: 600;
    padding: 0.6rem 1.4rem;
}
div.stButton > button[kind="primary"]:hover { background: #1b64da; }

h1 { font-weight: 700 !important; letter-spacing: -0.03em !important; color: #18181b !important; }
</style>
""",
    unsafe_allow_html=True,
)


def _init_session_state() -> None:
    if "settings" not in st.session_state:
        st.session_state.settings = load_settings()
    if "last_html" not in st.session_state:
        st.session_state.last_html = ""
    if "last_result" not in st.session_state:
        st.session_state.last_result = None
    if "scheduler_bootstrapped" not in st.session_state:
        st.session_state.scheduler_bootstrapped = False


def _run_newsletter_job(*, send_mail: bool = True) -> dict:
    """수집 → HTML 생성 → (선택) 발송."""
    settings = st.session_state.settings
    keywords = settings.get("keywords", [])
    recipients = settings.get("recipients", [])

    result: dict = {
        "articles": [],
        "errors": [],
        "send_result": None,
        "html_body": "",
        "subject": "",
    }

    collection = collect_all_news(
        keywords,
        hours_lookback=NEWS_HOURS_LOOKBACK,
        max_per_keyword=NEWS_MAX_PER_KEYWORD,
    )
    result["articles"] = collection.articles
    result["errors"] = collection.errors

    subject, html_body, _plain = build_newsletter_content(
        collection.articles,
        keywords,
        title=settings.get("custom_title", ""),
        intro=settings.get("intro", ""),
        hours_lookback=NEWS_HOURS_LOOKBACK,
    )
    result["subject"] = subject
    result["html_body"] = html_body
    st.session_state.last_html = html_body

    if send_mail and recipients:
        send_result = send_newsletter(
            collection.articles,
            keywords,
            recipients,
            title=settings.get("custom_title", ""),
            intro=settings.get("intro", ""),
            hours_lookback=NEWS_HOURS_LOOKBACK,
        )
        result["send_result"] = send_result
    elif send_mail and not recipients:
        result["errors"].append("수신자 이메일이 등록되지 않아 발송을 건너뛰었습니다.")

    st.session_state.last_result = result
    return result


def _scheduled_job() -> None:
    """APScheduler가 호출하는 백그라운드 작업."""
    try:
        settings = load_settings()
        keywords = settings.get("keywords", [])
        recipients = settings.get("recipients", [])
        if not keywords:
            logger.warning("Scheduled job skipped: no keywords")
            return

        collection = collect_all_news(keywords)
        if recipients:
            send_newsletter(
                collection.articles,
                keywords,
                recipients,
                title=settings.get("custom_title", ""),
                intro=settings.get("intro", ""),
            )
            logger.info("Scheduled newsletter sent (%d articles)", len(collection.articles))
        else:
            logger.warning("Scheduled job: collected %d articles but no recipients", len(collection.articles))
    except Exception as exc:
        logger.exception("Scheduled job failed: %s", exc)


def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### ⚙️ 설정")
        st.caption("키워드 · 수신자 · 연동 상태")

        st.markdown("#### 🔖 추적 키워드")
        new_kw = st.text_input("키워드 추가", placeholder="예: AI, 반도체", label_visibility="collapsed")
        col_add, _ = st.columns([1, 1])
        with col_add:
            if st.button("추가", use_container_width=True, key="add_kw"):
                if new_kw.strip():
                    st.session_state.settings = add_keyword(new_kw, st.session_state.settings)
                    save_settings(st.session_state.settings)
                    st.rerun()

        keywords = st.session_state.settings.get("keywords", [])
        if keywords:
            for kw in keywords:
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f'<span class="tag-chip">{kw}</span>', unsafe_allow_html=True)
                with c2:
                    if st.button("✕", key=f"rm_kw_{kw}"):
                        st.session_state.settings = remove_keyword(kw, st.session_state.settings)
                        save_settings(st.session_state.settings)
                        st.rerun()
        else:
            st.info("등록된 키워드가 없습니다.")

        st.divider()

        st.markdown("#### 📧 수신자 이메일")
        new_email = st.text_input("이메일 추가", placeholder="name@company.com", label_visibility="collapsed")
        if st.button("수신자 추가", use_container_width=True, key="add_email"):
            if new_email.strip() and "@" in new_email:
                st.session_state.settings = add_recipient(new_email, st.session_state.settings)
                save_settings(st.session_state.settings)
                st.rerun()
            else:
                st.error("유효한 이메일을 입력하세요.")

        recipients = st.session_state.settings.get("recipients", [])
        for em in recipients:
            c1, c2 = st.columns([4, 1])
            with c1:
                st.markdown(f"<small>{em}</small>", unsafe_allow_html=True)
            with c2:
                if st.button("✕", key=f"rm_em_{em}"):
                    st.session_state.settings = remove_recipient(em, st.session_state.settings)
                    save_settings(st.session_state.settings)
                    st.rerun()

        st.divider()

        st.markdown("#### 🔐 연동 상태")
        creds = credential_status()
        items = [
            ("네이버 API", creds["naver"]),
            ("Google RSS", creds["google_rss"]),
            ("Google API", creds["google_api"]),
            ("SMTP", creds["smtp"]),
        ]
        for label, ok in items:
            dot = "status-on" if ok else "status-off"
            text = "연결됨" if ok else "미설정"
            st.markdown(
                f'<span class="status-dot {dot}"></span>{label}: <b>{text}</b>',
                unsafe_allow_html=True,
            )

        st.divider()
        st.session_state.settings["intro"] = st.text_area(
            "인사말 (선택)", value=st.session_state.settings.get("intro", ""), height=80
        )
        st.session_state.settings["custom_title"] = st.text_input(
            "커스텀 제목 (선택)", value=st.session_state.settings.get("custom_title", "")
        )
        if st.button("설정 저장", use_container_width=True):
            save_settings(st.session_state.settings)
            st.success("저장되었습니다.")


def _render_dashboard() -> None:
    st.markdown("# 📬 Keyword Newsletter")
    st.caption("키워드 기반 뉴스 자동 수집 · 매일 아침 8시 발송")

    running = is_scheduler_running()
    next_run = get_next_run_time()
    keywords = st.session_state.settings.get("keywords", [])
    recipients = st.session_state.settings.get("recipients", [])

    c1, c2, c3 = st.columns(3)
    with c1:
        dot = "status-on" if running else "status-off"
        status_text = "작동 중" if running else "중지됨"
        st.markdown(
            f"""<div class="stat-card">
            <div class="stat-label">스케줄러</div>
            <div class="stat-value"><span class="status-dot {dot}"></span>{status_text}</div>
            <div class="stat-sub">매일 {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} ({SCHEDULE_TIMEZONE})</div>
            </div>""",
            unsafe_allow_html=True,
        )
    with c2:
        next_str = next_run.strftime("%m/%d %H:%M") if next_run else "—"
        st.markdown(
            f"""<div class="stat-card">
            <div class="stat-label">다음 발송 예정</div>
            <div class="stat-value">{next_str}</div>
            <div class="stat-sub">자동 발송 일정</div>
            </div>""",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f"""<div class="stat-card">
            <div class="stat-label">등록 키워드</div>
            <div class="stat-value">{len(keywords)}</div>
            <div class="stat-sub">키워드당 최대 {NEWS_MAX_PER_KEYWORD}건 · {NEWS_HOURS_LOOKBACK}h</div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    col_btn, col_info = st.columns([1, 2])
    with col_btn:
        if st.button("🚀 지금 수집 및 테스트 발송", type="primary", use_container_width=True):
            if not keywords:
                st.error("먼저 사이드바에서 키워드를 등록하세요.")
            elif not recipients:
                st.warning("수신자가 없습니다. 수집만 진행합니다.")
                with st.spinner("뉴스 수집 중..."):
                    result = _run_newsletter_job(send_mail=False)
                st.success(f"수집 완료 — {len(result['articles'])}건")
            else:
                with st.spinner("뉴스 수집 및 발송 중..."):
                    result = _run_newsletter_job(send_mail=True)
                if result.get("send_result") and result["send_result"]["success"]:
                    st.success(result["send_result"]["message"])
                elif result.get("send_result"):
                    st.error(result["send_result"]["message"])
                else:
                    st.success(f"수집 완료 — {len(result['articles'])}건")

    with col_info:
        st.markdown(
            f"<small>수신자 **{len(recipients)}**명 · "
            f"수집 기준: 발송 시점 기준 최근 **{NEWS_HOURS_LOOKBACK}시간**</small>",
            unsafe_allow_html=True,
        )

    last = st.session_state.last_result
    if last and last.get("errors"):
        with st.expander("⚠️ 수집/발송 경고", expanded=False):
            for err in last["errors"]:
                st.warning(err)

    st.divider()
    st.markdown("### 📰 Newsletter Preview")
    html_to_show = st.session_state.last_html
    if html_to_show:
        components.html(html_to_show, height=720, scrolling=True)
    else:
        st.markdown(
            '<div style="text-align:center;padding:60px;background:#fafafa;border-radius:12px;'
            'border:1px dashed #e4e4e7;color:#71717a;">'
            "「지금 수집 및 테스트 발송」 버튼을 눌러 미리보기를 생성하세요.</div>",
            unsafe_allow_html=True,
        )


def main() -> None:
    _init_session_state()

    if not st.session_state.scheduler_bootstrapped:
        start_daily_scheduler(_scheduled_job)
        st.session_state.scheduler_bootstrapped = True

    _render_sidebar()
    _render_dashboard()


if __name__ == "__main__":
    main()
