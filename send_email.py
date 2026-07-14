#!/usr/bin/env python3
"""send_email.py — 通过 QQ邮箱 SMTP 发送日报邮件（含微信/小红书附件）"""

import json, logging, os, smtplib, sys
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(WORK_DIR, "output")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

QQ_EMAIL = os.environ.get("QQ_EMAIL", "")
QQ_EMAIL_AUTH_CODE = os.environ.get("QQ_EMAIL_AUTH_CODE", "")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "")
SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 587


def load_latest(prefix, suffix):
    fs = [f for f in os.listdir(OUTPUT_DIR) if f.startswith(prefix) and f.endswith(suffix)]
    if not fs: return None
    p = os.path.join(OUTPUT_DIR, max(fs))
    with open(p, "r", encoding="utf-8") as f: return f.read(), os.path.basename(p)


def load_latest_json():
    for prefix in ["papers_translated_", "papers_raw_"]:
        fs = [f for f in os.listdir(OUTPUT_DIR) if f.startswith(prefix) and f.endswith(".json")]
        if fs:
            p = os.path.join(OUTPUT_DIR, max(fs))
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    return {"papers": []}


def make_attachment(content, filename):
    part = MIMEText(content, "plain", "utf-8")
    part.add_header("Content-Disposition", "attachment", filename=("utf-8", "", filename))
    return part


def clean_date(value):
    if not value:
        return "日期信息不完整"
    return value[:10] if len(value) >= 10 else "日期信息不完整"


def build_plain_text(date_tag):
    data = load_latest_json()
    papers = data.get("papers", [])
    lines = [
        "天然产物与 P450 工程每日文献简报",
        f"推送日期：{date_tag}",
        "",
        f"本期共筛选文献 {len(papers)} 篇，覆盖 P450/CPR、酵母底盘、天然产物生物合成及 AI 辅助酶工程等方向。",
        "",
    ]
    for i, paper in enumerate(papers, 1):
        title_cn = paper.get("title_cn") or "中文标题待补充"
        title_en = paper.get("title_en") or paper.get("title") or "English title unavailable"
        summary = paper.get("summary_cn_short") or "该文献摘要信息尚未完成结构化处理，请查看 HTML 版或原文链接。"
        relevance = paper.get("relevance_cn") or "该文献与当前研究方向的具体关联仍需进一步判断。"
        url = paper.get("url") or (f"https://doi.org/{paper.get('doi')}" if paper.get("doi") else "")
        lines.extend([
            f"{i:02d}",
            f"见刊日期：{clean_date(paper.get('publication_date'))}",
            f"中文标题：{title_cn}",
            f"English Title: {title_en}",
            f"内容摘要：{summary}",
            f"研究相关性：{relevance}",
        ])
        if url:
            lines.append(f"原文链接：{url}")
        lines.append("")
    lines.append("本邮件由自动化文献检索与摘要系统生成。")
    return "\n".join(lines)


def send_email(html_content, date_tag, is_test=False):
    if not QQ_EMAIL or not QQ_EMAIL_AUTH_CODE or not RECIPIENT_EMAIL:
        log.error("环境变量未设置"); return False

    subject = f"[每日文献简报] 天然产物与 P450 工程方向精选文献 {date_tag}"
    if is_test: subject = f"[测试] {subject}"

    msg = MIMEMultipart("mixed")
    msg["From"] = formataddr((str(Header("天然产物与 P450 工程文献简报", "utf-8")), QQ_EMAIL))
    msg["To"] = RECIPIENT_EMAIL
    msg["Subject"] = Header(subject, "utf-8")

    # 正文部分（plain + html）
    body = MIMEMultipart("alternative")
    body.attach(MIMEText(build_plain_text(date_tag), "plain", "utf-8"))
    body.attach(MIMEText(html_content, "html", "utf-8"))
    msg.attach(body)

    # 附件：微信文章 + 小红书文案
    for prefix, fname, label in [
        ("wechat_article_", "微信公众号文章.txt", "微信"),
        ("xiaohongshu_", "小红书文案.txt", "小红书"),
    ]:
        result = load_latest(prefix, ".md")
        if result:
            content, _ = result
            msg.attach(make_attachment(content, fname))
            log.info(f"已附加附件: {fname}")
        else:
            log.warning(f"未找到{label}文件，跳过附件")

    try:
        log.info(f"连接 SMTP 服务器 {SMTP_SERVER}:{SMTP_PORT}")
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(QQ_EMAIL, QQ_EMAIL_AUTH_CODE)
        server.sendmail(QQ_EMAIL, [RECIPIENT_EMAIL], msg.as_string())
        server.quit()
        log.info(f"邮件发送成功 -> {RECIPIENT_EMAIL}")
        return True
    except smtplib.SMTPAuthenticationError:
        log.error("SMTP 认证失败，请检查 QQ邮箱 和 授权码")
        return False
    except smtplib.SMTPRecipientsRefused:
        log.error(f"收件人 {RECIPIENT_EMAIL} 被拒绝")
        return False
    except Exception as e:
        log.error(f"发送失败: {e}")
        return False


def main():
    log.info("=" * 40); log.info("邮件发送(含附件)"); log.info("=" * 40)
    is_test = "--test" in sys.argv

    result = load_latest("daily_report_", ".html")
    if not result: sys.exit(1)
    html_content, filename = result
    date_tag = filename.replace("daily_report_", "").replace(".html", "")
    if not date_tag: date_tag = datetime.now().strftime("%Y-%m-%d")

    log.info(f"加载 HTML: {filename}")

    if send_email(html_content, date_tag, is_test):
        print(f"{'[TEST]' if is_test else '[OK]'} 邮件已发送 -> {RECIPIENT_EMAIL}")
    else:
        print("[FAILED] 邮件发送失败"); sys.exit(1)


if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: sys.exit(1)
    except Exception as e: log.error(f"失败: {e}"); import traceback; traceback.print_exc(); sys.exit(1)
