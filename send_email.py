#!/usr/bin/env python3
"""send_email.py — 通过 QQ邮箱 SMTP 发送日报邮件"""

import logging, os, smtplib, sys
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(WORK_DIR, "output")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

# 配置（从环境变量读取）
QQ_EMAIL = os.environ.get("QQ_EMAIL", "")
QQ_EMAIL_AUTH_CODE = os.environ.get("QQ_EMAIL_AUTH_CODE", "")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "")

SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 587


def load_latest_html():
    """加载最新的 daily_report_*.html"""
    fs = [f for f in os.listdir(OUTPUT_DIR) if f.startswith("daily_report_") and f.endswith(".html")]
    if not fs:
        log.error("未找到 daily_report_*.html 文件")
        return None
    p = os.path.join(OUTPUT_DIR, max(fs))
    with open(p, "r", encoding="utf-8") as f:
        return f.read(), os.path.basename(p)


def send_email(html_content, date_tag, is_test=False):
    """发送邮件"""
    if not QQ_EMAIL or not QQ_EMAIL_AUTH_CODE or not RECIPIENT_EMAIL:
        log.error("环境变量未设置: QQ_EMAIL / QQ_EMAIL_AUTH_CODE / RECIPIENT_EMAIL")
        return False

    subject = f"[AI+酶工程] 每日文献速递 {date_tag}"
    if is_test:
        subject = f"[测试] {subject}"

    msg = MIMEMultipart("alternative")
    msg["From"] = f"AI+酶工程 文献推送 <{QQ_EMAIL}>"
    msg["To"] = RECIPIENT_EMAIL
    msg["Subject"] = Header(subject, "utf-8")

    # 纯文本备用
    text_part = MIMEText(
        f"AI+酶工程 每日文献速递 {date_tag}\n\n"
        f"请查看此邮件 HTML 版本以获取完整内容。\n\n"
        f"由自动推送系统生成",
        "plain", "utf-8"
    )
    msg.attach(text_part)

    # HTML 正文
    html_part = MIMEText(html_content, "html", "utf-8")
    msg.attach(html_part)

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
        log.error("SMTP 认证失败，请检查 QQ邮箱 和 授权码 是否正确")
        return False
    except smtplib.SMTPRecipientsRefused:
        log.error(f"收件人 {RECIPIENT_EMAIL} 被拒绝")
        return False
    except Exception as e:
        log.error(f"发送失败: {e}")
        return False


def main():
    log.info("=" * 40)
    log.info("邮件发送")
    log.info("=" * 40)

    # 检查参数
    is_test = "--test" in sys.argv

    result = load_latest_html()
    if result is None:
        sys.exit(1)
    html_content, filename = result

    # 从文件名提取日期
    date_tag = filename.replace("daily_report_", "").replace(".html", "")
    if not date_tag:
        date_tag = datetime.now().strftime("%Y-%m-%d")

    log.info(f"加载 HTML: {filename}")

    success = send_email(html_content, date_tag, is_test)
    if success:
        label = "[TEST]" if is_test else "[OK]"
        print(f"{label} 邮件已发送 -> {RECIPIENT_EMAIL}")
    else:
        print(f"[FAILED] 邮件发送失败")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as e:
        log.error(f"失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
