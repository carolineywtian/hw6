"""Problem 5: open every vendor document the way a person would, and save a picture of what they see.

    source .venv/bin/activate
    python person_view.py                      # all practice docs
    python person_view.py data/exam_docs       # another folder

    HTML  -> Google Chrome (headless), the same engine as a normal browser window
    PDF   -> macOS Quick Look, the same PDF renderer as Preview
    .eml  -> rendered like an email app: From/To/Subject/Date header, then the HTML body if the email
             has one (Apple Mail shows the HTML version of a multipart/alternative email), else the
             plain-text body. That page is then rendered in Chrome.

Pictures go to output/person_view/<document>.png
"""

from __future__ import annotations

import html
import shutil
import subprocess
import sys
import tempfile
from email import policy
from email.parser import BytesParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "output" / "person_view"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def chrome_screenshot(page: Path, png: Path, profile: str) -> None:
    subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--no-first-run", f"--user-data-dir={profile}",
         "--window-size=900,1000", "--hide-scrollbars", f"--screenshot={png}", page.resolve().as_uri()],
        check=True, capture_output=True, timeout=60,
    )


def quicklook_png(pdf: Path, png: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["qlmanage", "-t", "-s", "1100", "-o", tmp, str(pdf)], check=True, capture_output=True, timeout=60)
        shutil.move(Path(tmp) / f"{pdf.name}.png", png)


def email_as_mail_app_page(eml: Path) -> str:
    msg = BytesParser(policy=policy.default).parsebytes(eml.read_bytes())
    head = "".join(
        f"<div><b style='color:#666'>{h}:</b> {html.escape(str(msg[h]))}</div>" for h in ("From", "To", "Subject", "Date") if msg[h]
    )
    part = msg.get_body(preferencelist=("html", "plain"))
    content = part.get_content() if part else ""
    body = content if part and part.get_content_type() == "text/html" else f"<div style='white-space:pre-wrap'>{html.escape(content)}</div>"
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'></head>"
        "<body style='font-family:-apple-system,Helvetica,sans-serif;background:#fff;margin:24px;max-width:820px'>"
        f"<div style='border-bottom:1px solid #ddd;padding-bottom:10px;margin-bottom:16px;font-size:14px'>{head}</div>"
        f"<div style='font-size:15px'>{body}</div></body></html>"
    )


def render(doc: Path, profile: str, tmp: Path) -> Path:
    png = OUT_DIR / f"{doc.stem}.png"
    suffix = doc.suffix.lower()
    if suffix in (".html", ".htm"):
        chrome_screenshot(doc, png, profile)
    elif suffix == ".pdf":
        quicklook_png(doc, png)
    elif suffix == ".eml":
        page = tmp / f"{doc.stem}.html"
        page.write_text(email_as_mail_app_page(doc), encoding="utf-8")
        chrome_screenshot(page, png, profile)
    else:
        raise ValueError(f"Unsupported document type: {doc.name}")
    return png


def main() -> None:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "data" / "practice_docs"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as profile, tempfile.TemporaryDirectory() as tmp:
        for doc in sorted(folder.iterdir()):
            if doc.suffix.lower() in (".html", ".htm", ".pdf", ".eml"):
                print(f"{doc.name:32} -> {render(doc, profile, Path(tmp)).relative_to(HERE)}")


if __name__ == "__main__":
    main()
