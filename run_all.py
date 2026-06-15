#!/usr/bin/env python3
"""run_all.py — 总调度脚本：抓取→翻译→生成HTML→发送邮件"""

import logging, os, subprocess, sys, time

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(WORK_DIR)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

STEPS = [
    ("daily_paper_list.py",  "抓取论文",     True),    # 必须成功
    ("translate.py",         "摘要翻译",     False),   # 可选
    ("format_html.py",       "生成HTML",     False),   # 可选
    ("send_email.py",        "发送邮件",     False),   # 可选
]


def run_step(script, label, required):
    log.info(f"{'='*20} {label} {'='*20}")
    log.info(f"执行: python {script}")
    start = time.time()
    result = subprocess.run(
        [sys.executable, script],
        capture_output=True, text=True
    )
    elapsed = time.time() - start

    # 打印输出
    for line in result.stdout.strip().split("\n"):
        if line.strip():
            log.info(f"  {line.strip()}")
    if result.stderr.strip():
        for line in result.stderr.strip().split("\n"):
            if line.strip():
                log.warning(f"  [stderr] {line.strip()}")

    if result.returncode == 0:
        log.info(f"✓ {label} 完成 ({elapsed:.1f}s)")
        return True
    else:
        log.error(f"✗ {label} 失败 (退出码 {result.returncode}, {elapsed:.1f}s)")
        if required:
            log.error("此步骤为必需步骤，终止后续执行")
            return False
        else:
            log.warning("此步骤为可选步骤，继续执行后续步骤")
            return True


def main():
    log.info("=" * 50)
    log.info("AI+酶工程 每日文献推送 — 全流程")
    log.info("=" * 50)

    all_ok = True
    for script, label, required in STEPS:
        ok = run_step(script, label, required)
        if not ok:
            all_ok = False
            break

    if all_ok:
        log.info("=" * 50)
        log.info("全流程执行成功 ✓")
        log.info("=" * 50)
    else:
        log.error("全流程执行失败 ✗")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as e:
        log.error(f"异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
