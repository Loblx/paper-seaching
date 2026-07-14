#!/usr/bin/env python3
"""translate.py — 使用 DeepSeek API 生成中文标题、摘要和相关性说明"""

import json, logging, os, re, sys, time
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

SYSTEM_PROMPT = """你是一个专业的学术文献简报编辑。你的任务是为天然产物、P450/CPR、酵母底盘和AI酶工程方向生成正式、准确、便于快速阅读的中文文献信息。
要求：
1. 保持学术表达严谨、正式、准确
2. 专业术语翻译准确，例如 cytochrome P450 译为“细胞色素 P450”，enzyme engineering 译为“酶工程”
3. 保留必要缩写、专有名词、数字和物种名
4. 不使用口语化表达，不使用“值得看看”“点开”等措辞
5. 只输出 JSON，不要输出 Markdown 或解释文字

JSON 字段：
{
  "title_cn": "中文标题",
  "abstract_cn": "完整中文摘要",
  "summary_cn_short": "2-3句正式中文内容摘要",
  "relevance_cn": "1-2句说明该文献与P450/CPR、底盘细胞、天然产物或AI酶工程的相关性"
}"""


def load_latest_raw():
    """加载最新的 papers_raw_*.json"""
    fs = [f for f in os.listdir(OUTPUT_DIR) if f.startswith("papers_raw_") and f.endswith(".json")]
    if not fs:
        log.error("未找到 papers_raw_*.json 文件")
        return None
    p = os.path.join(OUTPUT_DIR, max(fs))
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f), p


def extract_json(text):
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    match = re.search(r"\{.*\}", text, flags=re.S)
    if match:
        text = match.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def make_brief(client, title, abstract_text, topics):
    """调用 DeepSeek API 生成单篇文献简报字段"""
    if not title and not abstract_text:
        return {}
    try:
        user_content = {
            "title_en": title or "",
            "abstract_en": abstract_text or "",
            "research_topics": topics or [],
        }
        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "请根据以下论文信息生成 JSON：\n" + json.dumps(user_content, ensure_ascii=False)}
            ],
            temperature=0.3,
            max_tokens=2048,
        )
        result = extract_json(resp.choices[0].message.content)
        if not isinstance(result, dict):
            raise ValueError("模型未返回有效 JSON")
        return result
    except Exception as e:
        log.warning(f"简报生成失败: {e}")
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

    # 逐篇生成文献简报
    translated = 0
    skipped = 0
    failed = 0
    for i, paper in enumerate(papers):
        title = paper.get("title", "N/A")[:60]
        abstract = paper.get("abstract", "")

        # 跳过已有完整简报字段的论文
        if paper.get("title_cn") and paper.get("abstract_cn") and paper.get("summary_cn_short"):
            log.info(f"  [{i+1}/{len(papers)}] 已有简报，跳过: {title}")
            skipped += 1
            continue

        log.info(f"  [{i+1}/{len(papers)}] 生成简报: {title}")
        result = make_brief(client, paper.get("title", ""), abstract, paper.get("research_topics", []))

        if result is not None:
            paper["title_en"] = paper.get("title", "")
            paper["title_cn"] = result.get("title_cn", "").strip()
            paper["abstract_cn"] = result.get("abstract_cn", "").strip()
            paper["summary_cn_short"] = result.get("summary_cn_short", "").strip()
            paper["relevance_cn"] = result.get("relevance_cn", "").strip()
            translated += 1
        else:
            paper["title_en"] = paper.get("title", "")
            paper["title_cn"] = ""
            paper["abstract_cn"] = "[翻译失败]"
            paper["summary_cn_short"] = ""
            paper["relevance_cn"] = ""
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

    log.info(f"简报生成完成: 新增{translated}, 跳过{skipped}, 失败{failed}")
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
