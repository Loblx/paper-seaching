#!/usr/bin/env python3
"""translate.py — 使用 DeepSeek API 将论文摘要从英文翻译为中文"""

import json, logging, os, sys, time
from datetime import datetime
from openai import OpenAI

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(WORK_DIR, "output")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

# 配置（从环境变量读取）
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
API_DELAY = 1.0  # 每次调用间隔，避免限流

SYSTEM_PROMPT = """你是一个专业的学术论文翻译助手。你的任务是将英文论文摘要翻译成流畅、准确的中文。
要求：
1. 保持学术翻译的严谨性和准确性
2. 专业术语翻译要准确，如 "machine learning" → "机器学习"，"enzyme" → "酶"
3. 中文表达要自然流畅，符合中文阅读习惯
4. 保留原文中的数字、缩写、专有名词（如 ProteinMPNN、AlphaFold 等）
5. 只输出翻译结果，不要添加任何解释或额外内容"""


def load_latest_raw():
    """加载最新的 papers_raw_*.json"""
    fs = [f for f in os.listdir(OUTPUT_DIR) if f.startswith("papers_raw_") and f.endswith(".json")]
    if not fs:
        log.error("未找到 papers_raw_*.json 文件")
        return None
    p = os.path.join(OUTPUT_DIR, max(fs))
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f), p


def translate_abstract(client, abstract_text):
    """调用 DeepSeek API 翻译单篇摘要"""
    if not abstract_text or len(abstract_text.strip()) < 10:
        return ""
    try:
        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"请将以下英文论文摘要翻译为中文：\n\n{abstract_text}"}
            ],
            temperature=0.3,
            max_tokens=2048,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        log.warning(f"翻译失败: {e}")
        return None


def main():
    log.info("=" * 40)
    log.info("DeepSeek 摘要翻译")
    log.info("=" * 40)

    if not DEEPSEEK_API_KEY:
        log.error("环境变量 DEEPSEEK_API_KEY 未设置")
        sys.exit(1)

    # 加载数据
    result = load_latest_raw()
    if result is None:
        sys.exit(1)
    data, source_path = result
    papers = data.get("papers", [])
    today = datetime.now().strftime("%Y-%m-%d")
    log.info(f"加载 {len(papers)} 篇论文，来自 {os.path.basename(source_path)}")

    # 初始化 DeepSeek 客户端
    client = OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com"
    )

    # 逐篇翻译
    translated = 0
    skipped = 0
    failed = 0
    for i, paper in enumerate(papers):
        title = paper.get("title", "N/A")[:60]
        abstract = paper.get("abstract", "")

        # 跳过已有翻译的
        if paper.get("abstract_cn"):
            log.info(f"  [{i+1}/{len(papers)}] 已有翻译，跳过: {title}")
            skipped += 1
            continue

        log.info(f"  [{i+1}/{len(papers)}] 翻译中: {title}")
        result = translate_abstract(client, abstract)

        if result is not None:
            paper["abstract_cn"] = result
            translated += 1
        else:
            paper["abstract_cn"] = "[翻译失败]"
            failed += 1

        # 控制调用频率
        if i < len(papers) - 1:
            time.sleep(API_DELAY)

    # 保存结果
    data["translated_at"] = datetime.now().isoformat()
    data["translation_stats"] = {
        "total": len(papers),
        "translated": translated,
        "skipped": skipped,
        "failed": failed
    }

    output_path = os.path.join(OUTPUT_DIR, f"papers_translated_{today}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    log.info(f"翻译完成: 新增{translated}, 跳过{skipped}, 失败{failed}")
    log.info(f"已保存: {output_path}")
    print(f"[OK] 翻译结果 -> {output_path}")


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
