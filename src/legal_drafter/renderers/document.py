from __future__ import annotations

import html
import secrets
import tempfile
from dataclasses import replace
from pathlib import Path

from legal_drafter.catalog import get_category_spec
from legal_drafter.exceptions import RenderError
from legal_drafter.models import DocumentResult, RenderOptions, RenderedArtifact, ReviewPolicy, ValidationSeverity


def render_document(result: DocumentResult, options: RenderOptions | None = None) -> DocumentResult:
    resolved_options = options or RenderOptions()
    spec = get_category_spec(result.category_id)
    if spec.review_policy == ReviewPolicy.PROCEDURAL_STRICT and any(
        issue.severity == ValidationSeverity.ERROR for issue in result.validation_issues
    ):
        raise RenderError("procedural documents require all mandatory fields before rendering artifacts")

    token = resolved_options.artifact_token or secrets.token_hex(8)
    root = resolved_options.artifact_root or Path(tempfile.gettempdir()) / "legal_drafter_artifacts"
    artifact_dir = Path(root) / token
    artifact_dir.mkdir(parents=True, exist_ok=True)

    html_path = artifact_dir / "document.html"
    pdf_path = artifact_dir / "document.pdf"
    html_text = _build_print_html(result, spec.render_profile.get("footer_notice"))
    html_path.write_text(html_text, encoding="utf-8")

    png_paths = _render_with_playwright(html_path=html_path, pdf_path=pdf_path)
    artifacts = [
        RenderedArtifact(
            name=html_path.name,
            kind="html",
            path=html_path,
            content_type="text/html; charset=utf-8",
            url=_build_artifact_url(resolved_options.artifact_base_url, token, html_path.name),
        ),
        RenderedArtifact(
            name=pdf_path.name,
            kind="pdf",
            path=pdf_path,
            content_type="application/pdf",
            url=_build_artifact_url(resolved_options.artifact_base_url, token, pdf_path.name),
        ),
    ]
    artifacts.extend(
        RenderedArtifact(
            name=path.name,
            kind="png",
            path=path,
            content_type="image/png",
            url=_build_artifact_url(resolved_options.artifact_base_url, token, path.name),
        )
        for path in png_paths
    )
    return replace(result, rendered_artifacts=tuple(artifacts))


def _build_print_html(result: DocumentResult, footer_notice: str | None) -> str:
    pages = _paginate_sections(result)
    appendix_markup = _build_appendix_markup(result)
    total_pages = len(pages) + (1 if appendix_markup else 0)
    page_markup = []
    for page_index, sections in enumerate(pages, start=1):
        section_blocks = []
        if page_index == 1:
            section_blocks.append(
                f"""
                <header class="doc-header">
                  <h1>{html.escape(result.title)}</h1>
                </header>
                """
            )
        for section in sections:
            section_blocks.append(
                f"""
                <section class="section">
                  <h2>{html.escape(section.heading)}</h2>
                  <div class="body">{_paragraphize(section.body)}</div>
                </section>
                """
            )
        footer_markup = html.escape(footer_notice or "본 문서는 참고용 초안입니다.") if page_index == total_pages else ""
        page_markup.append(
            f"""
            <article class="page">
              <div class="watermark">Sample</div>
              <div class="page-inner">
                {''.join(section_blocks)}
              </div>
              <footer class="page-footer">
                <span>{footer_markup}</span>
                <span>{page_index} / {total_pages}</span>
              </footer>
            </article>
            """
        )
    if appendix_markup:
        page_markup.append(
            f"""
            <article class="page appendix-page">
              <div class="watermark">Sample</div>
              <div class="page-inner appendix-inner">
                {appendix_markup}
              </div>
              <footer class="page-footer">
                <span>{html.escape(footer_notice or '본 문서는 참고용 초안입니다.')}</span>
                <span>{total_pages} / {total_pages}</span>
              </footer>
            </article>
            """
        )

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>{html.escape(result.title)}</title>
  <style>
    @page {{
      size: A4;
      margin: 0;
    }}
    :root {{
      --paper: #ffffff;
      --ink: #111111;
      --muted: #4b4b4b;
      --line: rgba(17, 17, 17, 0.12);
      --accent: #1a1a1a;
      --bg: #ece8de;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: "Batang", "Malgun Myeongjo", "Nanum Myeongjo", serif;
    }}
    .stack {{
      width: 100%;
      padding: 24px 0 48px;
      display: grid;
      gap: 22px;
      justify-items: center;
    }}
    .page {{
      width: 794px;
      min-height: 1123px;
      background: var(--paper);
      position: relative;
      box-shadow: 0 24px 60px rgba(17, 17, 17, 0.12);
      overflow: hidden;
    }}
    .watermark {{
      position: absolute;
      inset: 128px auto auto 64px;
      font-size: 102px;
      color: rgba(17, 17, 17, 0.04);
      transform: rotate(-28deg);
      letter-spacing: 0.08em;
      user-select: none;
    }}
    .page-inner {{
      padding: 122px 84px 120px;
      display: grid;
      gap: 42px;
    }}
    .doc-header {{
      display: grid;
      text-align: center;
      padding: 16px 0 28px;
    }}
    h1 {{
      margin: 0;
      font-size: 42px;
      letter-spacing: -0.05em;
      font-weight: 700;
    }}
    .section {{
      display: grid;
      gap: 18px;
    }}
    .section h2, .appendix h2 {{
      margin: 0;
      font-size: 24px;
      font-weight: 700;
      letter-spacing: -0.02em;
    }}
    .body {{
      display: grid;
      gap: 14px;
      font-size: 18.5px;
      line-height: 2.0;
      word-break: keep-all;
    }}
    .body p {{
      margin: 0;
      text-indent: 0;
    }}
    .citations, .issues {{
      margin: 0;
      padding-left: 20px;
      display: grid;
      gap: 8px;
      font-size: 13px;
      line-height: 1.7;
      color: var(--muted);
      font-family: "Malgun Gothic", sans-serif;
    }}
    .citations li, .issues li {{
      display: grid;
      gap: 4px;
    }}
    .muted {{
      margin: 0;
      font-size: 13px;
      color: var(--muted);
      font-family: "Malgun Gothic", sans-serif;
    }}
    .appendix {{
      display: grid;
      gap: 18px;
    }}
    .appendix-page .page-inner {{
      gap: 28px;
    }}
    .appendix-section {{
      display: grid;
      gap: 12px;
      font-family: "Malgun Gothic", sans-serif;
    }}
    .appendix-section h2 {{
      font-family: "Batang", "Malgun Myeongjo", serif;
    }}
    .page-footer {{
      position: absolute;
      left: 84px;
      right: 84px;
      bottom: 42px;
      display: flex;
      justify-content: space-between;
      gap: 16px;
      font-size: 12px;
      color: var(--muted);
      font-family: "Malgun Gothic", sans-serif;
      border-top: 1px solid var(--line);
      padding-top: 12px;
    }}
  </style>
</head>
<body>
  <main class="stack">
    {''.join(page_markup)}
  </main>
</body>
</html>
"""


def _build_appendix_markup(result: DocumentResult) -> str:
    sections: list[str] = []
    review_notes = [
        f"<li><strong>{html.escape(section.heading)}</strong> {html.escape(section.review_note)}</li>"
        for section in result.sections
        if section.review_note
    ]
    if review_notes:
        sections.append(
            f"""
            <section class="appendix-section">
              <h2>검토 메모</h2>
              <ul class="issues">{''.join(review_notes)}</ul>
            </section>
            """
        )
    if result.validation_issues:
        items = "".join(
            f"<li><strong>{html.escape(issue.path)}</strong> {html.escape(issue.message)}</li>"
            for issue in result.validation_issues
        )
        sections.append(
            f"""
            <section class="appendix-section">
              <h2>검토 포인트</h2>
              <ul class="issues">{items}</ul>
            </section>
            """
        )
    if result.citations:
        items = "".join(
            f"<li><strong>{html.escape(citation.reference)}</strong><span>{html.escape(citation.excerpt)}</span></li>"
            for citation in result.citations
        )
        sections.append(
            f"""
            <section class="appendix-section">
              <h2>참고 법령</h2>
              <ul class="citations">{items}</ul>
            </section>
            """
        )
    return "".join(sections)


def _paginate_sections(result: DocumentResult):
    pages: list[list] = []
    current_page: list = []
    current_score = 700
    for section in result.sections:
        score = 160 + len(section.heading) * 4 + len(section.body)
        threshold = 1700 if not pages else 2200
        if current_page and current_score + score > threshold:
            pages.append(current_page)
            current_page = []
            current_score = 0
        current_page.append(section)
        current_score += score
    if current_page:
        pages.append(current_page)
    return pages or [[]]


def _paragraphize(text: str) -> str:
    paragraphs = [part.strip() for part in text.replace("\r", "").split("\n") if part.strip()]
    if not paragraphs:
        return "<p>내용 없음</p>"
    return "".join(f"<p>{html.escape(paragraph)}</p>" for paragraph in paragraphs)


def _build_artifact_url(base_url: str | None, token: str, name: str) -> str | None:
    if not base_url:
        return None
    return f"{base_url}/{token}/{name}"


def _render_with_playwright(*, html_path: Path, pdf_path: Path) -> tuple[Path, ...]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise RenderError("Playwright is required for PDF/PNG rendering") from exc

    png_paths: list[Path] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 794, "height": 1123}, device_scale_factor=1)
            page.goto(html_path.as_uri(), wait_until="networkidle")
            page.pdf(path=str(pdf_path), format="A4", print_background=True, margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})
            page_locator = page.locator(".page")
            count = page_locator.count()
            if count <= 0:
                png_path = html_path.with_name("page-1.png")
                page.screenshot(path=str(png_path), full_page=True)
                png_paths.append(png_path)
            else:
                for index in range(count):
                    png_path = html_path.with_name(f"page-{index + 1}.png")
                    page_locator.nth(index).screenshot(path=str(png_path))
                    png_paths.append(png_path)
            browser.close()
    except Exception as exc:  # pragma: no cover
        raise RenderError("Playwright rendering failed") from exc
    return tuple(png_paths)
