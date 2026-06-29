"""뉴스레터 HTML / Plain 텍스트 템플릿."""

from datetime import datetime, timezone
from html import escape

from models import NewsArticle


def _format_korean_date(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    try:
        from zoneinfo import ZoneInfo

        kst = dt.astimezone(ZoneInfo("Asia/Seoul"))
    except Exception:
        kst = dt
    return kst.strftime("%Y-%m-%d %H:%M")


def _group_by_keyword(articles: list[NewsArticle]) -> dict[str, list[NewsArticle]]:
    grouped: dict[str, list[NewsArticle]] = {}
    for article in articles:
        grouped.setdefault(article.keyword, []).append(article)
    return grouped


def build_newsletter_title(keywords: list[str], custom_title: str = "") -> str:
    if custom_title.strip():
        return custom_title.strip()
    today = datetime.now().strftime("%m월 %d일")
    preview = ", ".join(keywords[:3])
    suffix = "..." if len(keywords) > 3 else ""
    return f"[Hanwha Newsletter] {today} 키워드 뉴스 ({preview}{suffix})"


def build_plain_body(
    articles: list[NewsArticle],
    keywords: list[str],
    hours_lookback: int,
    intro: str = "",
) -> str:
    lines = [
        intro.strip() or "안녕하세요. 설정하신 키워드 기반 최신 뉴스를 전해드립니다.",
        "",
        f"수집 기준: 발송 시점 기준 최근 {hours_lookback}시간",
        f"키워드: {', '.join(keywords)}",
        "",
    ]

    if not articles:
        lines.append("해당 기간 내 수집된 기사가 없습니다.")
        return "\n".join(lines)

    for keyword, items in _group_by_keyword(articles).items():
        lines.append(f"■ {keyword}")
        lines.append("-" * 40)
        for i, article in enumerate(items, 1):
            lines.append(f"{i}. {article.title}")
            lines.append(f"   {article.summary}")
            lines.append(f"   링크: {article.link}")
            if article.press:
                lines.append(f"   출처: {article.press}")
            lines.append("")
        lines.append("")

    lines.append("— Hanwha Newsletter")
    return "\n".join(lines)


def build_html_body(
    articles: list[NewsArticle],
    keywords: list[str],
    hours_lookback: int,
    title: str,
    intro: str = "",
) -> str:
    """토스/노션 스타일 카드 UI 인라인 CSS HTML."""
    intro_text = escape(
        intro.strip() or "안녕하세요. 설정하신 키워드 기반 최신 뉴스를 전해드립니다."
    )
    sent_date = datetime.now().strftime("%Y년 %m월 %d일")
    safe_title = escape(title)

    keyword_tags = "".join(
        f'<span style="display:inline-block;background:#f4f4f5;color:#3f3f46;'
        f'padding:5px 12px;border-radius:20px;font-size:12px;font-weight:500;'
        f'margin:0 6px 6px 0;border:1px solid #e4e4e7;">{escape(kw)}</span>'
        for kw in keywords
    )

    if not articles:
        article_sections = (
            '<div style="text-align:center;padding:48px 24px;background:#fafafa;'
            'border-radius:12px;border:1px dashed #e4e4e7;">'
            '<p style="margin:0;font-size:15px;color:#71717a;">'
            f"해당 기간(최근 {hours_lookback}시간) 내 수집된 기사가 없습니다.</p></div>"
        )
    else:
        sections = []
        for keyword, items in _group_by_keyword(articles).items():
            cards = ""
            for article in items:
                source_color = "#3182f6" if article.source == "naver" else "#00a896"
                source_label = "네이버" if article.source == "naver" else "구글"
                press_html = (
                    f'<span style="color:#a1a1aa;"> · {escape(article.press)}</span>'
                    if article.press
                    else ""
                )
                pub = _format_korean_date(article.published_at)

                cards += f"""
                <div style="background:#ffffff;border:1px solid #e4e4e7;border-radius:12px;
                  padding:20px;margin-bottom:12px;box-shadow:0 1px 2px rgba(0,0,0,0.04);">
                  <div style="margin-bottom:10px;display:flex;align-items:center;flex-wrap:wrap;gap:6px;">
                    <span style="background:{source_color};color:#fff;font-size:11px;font-weight:600;
                      padding:3px 8px;border-radius:6px;">{source_label}</span>
                    <span style="font-size:12px;color:#a1a1aa;">{pub}{press_html}</span>
                  </div>
                  <h3 style="margin:0 0 8px;font-size:16px;font-weight:600;color:#18181b;line-height:1.45;">
                    <a href="{escape(article.link)}" style="color:#18181b;text-decoration:none;">
                      {escape(article.title)}
                    </a>
                  </h3>
                  <p style="margin:0 0 14px;font-size:14px;line-height:1.65;color:#52525b;">
                    {escape(article.summary)}
                  </p>
                  <a href="{escape(article.link)}" style="font-size:13px;color:#3182f6;
                    text-decoration:none;font-weight:600;">기사 원문 보기 →</a>
                </div>"""

            sections.append(f"""
            <div style="margin-bottom:32px;">
              <h2 style="margin:0 0 16px;font-size:17px;font-weight:700;color:#18181b;
                letter-spacing:-0.02em;">{escape(keyword)}</h2>
              {cards}
            </div>""")

        article_sections = "".join(sections)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
</head>
<body style="margin:0;padding:0;background:#f4f4f5;
  font-family:-apple-system,BlinkMacSystemFont,'Pretendard','Segoe UI',Roboto,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5;padding:40px 16px;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
  <tr>
    <td style="background:#ffffff;border-radius:16px 16px 0 0;padding:36px 32px 28px;
      border:1px solid #e4e4e7;border-bottom:none;">
      <p style="margin:0 0 6px;font-size:11px;color:#a1a1aa;font-weight:600;
        letter-spacing:0.08em;text-transform:uppercase;">Hanwha Newsletter</p>
      <h1 style="margin:0;font-size:22px;font-weight:700;color:#18181b;line-height:1.35;
        letter-spacing:-0.03em;">{safe_title}</h1>
      <p style="margin:10px 0 0;font-size:13px;color:#71717a;">{sent_date} · 최근 {hours_lookback}시간 뉴스</p>
    </td>
  </tr>
  <tr>
    <td style="background:#ffffff;padding:0 32px 8px;border-left:1px solid #e4e4e7;
      border-right:1px solid #e4e4e7;">{keyword_tags}</td>
  </tr>
  <tr>
    <td style="background:#ffffff;padding:24px 32px 32px;border:1px solid #e4e4e7;border-top:none;
      border-radius:0 0 16px 16px;">
      <p style="margin:0 0 28px;font-size:15px;line-height:1.7;color:#3f3f46;">{intro_text}</p>
      {article_sections}
    </td>
  </tr>
  <tr>
    <td style="padding:24px 16px;text-align:center;">
      <p style="margin:0;font-size:12px;color:#a1a1aa;line-height:1.6;">
        본 메일은 Hanwha Newsletter 시스템을 통해 발송되었습니다.<br>
        수집 소스: 네이버 뉴스 API · Google News RSS
      </p>
    </td>
  </tr>
</table>
</td></tr>
</table>
</body>
</html>"""
