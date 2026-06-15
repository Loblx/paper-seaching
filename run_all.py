#!/usr/bin/env python3
"""run_all.py — 全流程调度：抓取→翻译→生成HTML→微信→小红书→发送邮件"""

import logging, os, subprocess, sys, time

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(WORK_DIR)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

STEPS = [
    ("daily_paper_list.py",  "抓取论文",      True),
    ("translate.py",         "摘要翻译",      False),
    ("format_html.py",       "生成HTML",      False),
    ("format_wechat.py",     "微信文章",      False),
    ("format_xiaohongshu.py","小红书文案",    False),
    ("send_email.py",        "发送邮件",      False),
]

def run_step(script, label, required):
    log.info(f"{'='*20} {label} {'='*20}")
    log.info(f"执行: python {script}")
    start = time.time()
    result = subprocess.run([sys.executable, script], capture_output=True, text=True)
    elapsed = time.time() - start
    for line in result.stdout.strip().split("\n"):
        if line.strip(): log.info(f"  {line.strip()}")
    if result.stderr.strip():
        for line in result.stderr.strip().split("\n"):
            if line.strip(): log.warning(f"  [stderr] {line.strip()}")
    if result.returncode == 0:
        log.info(f"\u2713 {label} \u5b8c\u6210 ({elapsed:.1f}s)"); return True
    else:
        log.error(f"\u2717 {label} \u5931\u8d25 (\u9000\u51fa\u7801 {result.returncode}, {elapsed:.1f}s)")
        if required:
            log.error("此步骤为必需步骤，终止后续执行"); return False
        else:
            log.warning("此步骤为可选步骤，继续执行后续步骤"); return True

def main():
    log.info("="*50); log.info("AI+酶工程 每日文献推送 \u2014 \u5168\u6d41\u7a0b"); log.info("="*50)
    all_ok = True
    for script, label, required in STEPS:
        ok = run_step(script, label, required)
        if not ok: all_ok = False; break
    (log.info if all_ok else log.error)("="*50)
    if all_ok:
        log.info("全流程执行成功 \u2713")
    else:
        log.error("全流程执行失败 \u2717")
    log.info("="*50)
    if not all_ok: sys.exit(1)

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: sys.exit(1)
    except Exception as e: log.error(f"异常: {e}"); import traceback; traceback.print_exc(); sys.exit(1)
