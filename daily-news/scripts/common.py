#!/usr/bin/env python3
"""daily-news共用函数：API请求、AI调用、文件读写、推送接口。"""

import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from dotenv import load_dotenv
from openai import OpenAI

# 加载.env（沿目录树向上查找）
_env_path = Path(__file__).resolve().parents[3] / ".env"
if _env_path.is_file():
    load_dotenv(_env_path)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.join(SCRIPT_DIR, "..")
CONFIG_PATH = os.path.join(SKILL_DIR, "config.json")
STATE_PATH = os.path.join(SKILL_DIR, "state.json")
PROJECT_ROOT = os.path.abspath(os.path.join(SKILL_DIR, "..", ".."))


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_state() -> dict:
    if os.path.isfile(STATE_PATH):
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_timestamp": "", "last_newsid": ""}


def save_state(state: dict):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_raw_dir(config: dict) -> str:
    raw_dir = config["output"]["raw_dir"]
    if not os.path.isabs(raw_dir):
        raw_dir = os.path.join(PROJECT_ROOT, raw_dir)
    os.makedirs(raw_dir, exist_ok=True)
    return raw_dir


def get_raw_path(config: dict, date_str: str) -> str:
    return os.path.join(get_raw_dir(config), f"{date_str}_raw.json")


def get_daily_path(config: dict, date_str: str) -> str:
    return os.path.join(get_raw_dir(config), f"{date_str}_daily.md")


def get_alerts_path(config: dict, date_str: str) -> str:
    return os.path.join(get_raw_dir(config), f"{date_str}_alerts.md")


# ── 快兰斯API ──

def fetch_kualansi(url: str = None, config: dict = None) -> dict:
    """拉取快兰斯财经直播JSON，返回解析后的dict。"""
    if config is None:
        config = load_config()
    if url is None:
        api_url = config["sources"]["kualansi"]["api_url"]
        url = f"{api_url}?newsid=0"

    logger.info("拉取快兰斯: %s", url)
    try:
        req = Request(url)
        req.add_header("User-Agent", "Mozilla/5.0")
        with urlopen(req, timeout=15) as resp:
            raw = resp.read()
            encoding = config["sources"]["kualansi"].get("encoding", "utf-8-sig")
            text = raw.decode(encoding)
            return json.loads(text)
    except (URLError, HTTPError, json.JSONDecodeError) as e:
        logger.error("快兰斯API失败: %s", e)
        return {"list": [], "error": str(e)}


def fetch_kualansi_pages(start_time: str, config: dict = None) -> list:
    """翻页拉取快兰斯，直到时间早于start_time。返回所有新闻条目。"""
    if config is None:
        config = load_config()
    all_items = []
    url = None
    api_url = config["sources"]["kualansi"]["api_url"]

    while True:
        if url is None:
            url = f"{api_url}?newsid=0"
        data = fetch_kualansi(url, config)
        items = data.get("list", [])

        if not items:
            break

        for item in items:
            item_time = item.get("time", "")
            if item_time and item_time < start_time:
                return all_items
            all_items.append(item)

        next_page = data.get("nextpage", "")
        if not next_page:
            break
        url = next_page

    return all_items


# ── 金十数据 ──

def fetch_jin10(config: dict = None) -> str:
    """抓取金十数据页面HTML，返回纯文本摘要。简单提取文本内容。"""
    if config is None:
        config = load_config()
    url = config["sources"]["jin10"]["url"]
    logger.info("抓取金十: %s", url)
    try:
        req = Request(url)
        req.add_header("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)")
        with urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        # 简单提取：去HTML标签，保留文本
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        # 截取前5000字符，避免过长
        return text[:5000] if text else ""
    except (URLError, HTTPError) as e:
        logger.error("金十抓取失败: %s", e)
        return ""


# ── AI调用 ──

def get_ai_client(config: dict) -> OpenAI:
    ai_config = config["ai"]
    api_key = os.environ.get(ai_config["api_key_env"], "")
    if not api_key:
        logger.error("API Key未设置: %s", ai_config["api_key_env"])
        sys.exit(1)
    return OpenAI(api_key=api_key, base_url=ai_config["base_url"])


def call_ai(prompt: str, config: dict = None) -> str:
    """调用Kimi K2.7，返回AI回复文本。"""
    if config is None:
        config = load_config()
    client = get_ai_client(config)
    ai_config = config["ai"]

    logger.info("调用AI: %s", ai_config["model"])
    try:
        response = client.chat.completions.create(
            model=ai_config["model"],
            messages=[{"role": "user", "content": prompt}],
            max_tokens=ai_config.get("max_tokens", 8192),
            temperature=ai_config.get("temperature", 1),
            timeout=ai_config.get("timeout_seconds", 300),
        )
        choice = response.choices[0]
        content = choice.message.content or ""
        logger.info("AI响应: %d字符, finish_reason=%s", len(content), choice.finish_reason)
        return content
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("AI调用失败: %s", e)
        return ""


def build_holdings_text(config: dict) -> str:
    """构建持仓标的文本描述，供AI prompt使用。"""
    holdings = config["holdings"]
    lines = ["核心仓："]
    for h in holdings["core"]:
        lines.append(f"  - {h['name']}（{h['code']}）[{','.join(h['tags'])}]")
    lines.append("卫星仓：")
    for h in holdings["satellite"]:
        lines.append(f"  - {h['name']}（{h['code']}）[{','.join(h['tags'])}]")
    lines.append("宏观关注：" + "、".join(holdings["macro_focus"]))
    return "\n".join(lines)


# ── 关键词匹配 ──

def check_instant_alert(content: str, level: str, config: dict) -> bool:
    """检查是否触发即时推送：Level=2 且关键词命中。"""
    if level != "2":
        return False
    keywords = config["keywords"]["instant_alert"]
    for kw in keywords:
        if kw in content:
            return True
    return False


def is_quiet_hours(config: dict) -> bool:
    """判断当前是否在安静时段。"""
    schedule = config["schedule"]
    quiet = schedule.get("quiet_hours", {})
    if not quiet:
        return False
    now = datetime.now().strftime("%H:%M")
    start = quiet["start"]
    end = quiet["end"]
    if start > end:
        return now >= start or now < end
    return start <= now < end


def is_emergency_keyword(content: str, config: dict) -> bool:
    """检查是否包含极端事件关键词（安静时段仍推送）。"""
    for kw in config["keywords"].get("emergency_override", []):
        if kw in content:
            return True
    return False


# ── 文件读写 ──

def append_raw_news(items: list, config: dict, date_str: str = None):
    """追加新闻条目到当日原始快讯文件。"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    path = get_raw_path(config, date_str)

    existing = []
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            existing = json.load(f)

    existing_ids = {item.get("newsID") or item.get("time", "") for item in existing}
    new_items = []
    for item in items:
        item_id = item.get("newsID") or item.get("time", "")
        if item_id and item_id not in existing_ids:
            new_items.append(item)

    if new_items:
        existing.extend(new_items)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        logger.info("追加%d条新闻到 %s", len(new_items), path)

    return len(new_items)


def write_daily_report(content: str, config: dict, date_str: str = None):
    """写入AI日报MD文件。"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    path = get_daily_path(config, date_str)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info("日报写入: %s", path)


def append_alert(content: str, config: dict, date_str: str = None):
    """追加即时推送记录到alerts文件。"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    path = get_alerts_path(config, date_str)
    with open(path, "a", encoding="utf-8") as f:
        f.write(content + "\n\n")
    logger.info("推送记录追加: %s", path)


# ── 飞书推送（接口预留） ──

def send_feishu(message: str, _config: dict):
    """飞书推送接口。具体实现由OpenClaw调试对接。"""
    logger.info("[飞书推送-预留] %s", message[:100])
    # TODO: OpenClaw对接飞书推送
    # target = config["output"].get("feishu_target", "")
    # 调用openclaw message工具推送


# ── 去重 ──

def deduplicate_news(items: list) -> list:
    """按newsID+time去重。"""
    seen = set()
    result = []
    for item in items:
        key = (item.get("newsID"), item.get("time", ""))
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def filter_noise(items: list, config: dict) -> list:
    """预筛选：用noise_filter关键词过滤明显噪音新闻。"""
    noise_keywords = config.get("keywords", {}).get("noise_filter", [])
    if not noise_keywords:
        return items
    filtered = []
    for item in items:
        content = item.get("content", "")
        if any(kw in content for kw in noise_keywords):
            continue
        filtered.append(item)
    logger.info("噪音过滤: %d → %d（过滤%d条）", len(items), len(filtered), len(items) - len(filtered))
    return filtered


# ── Prompt模板 ──

PROMPT_INSTANT = """你是一个专业的财经新闻分析师。请分析以下新闻：

{content}

持仓标的：
{holdings}

请输出：
1. 核心观点（一句话）
2. 影响标的（如有）
3. 情绪方向（多/空/中性）
4. 是否需要立即关注（是/否）"""

PROMPT_DAILY = """你是一个专业的财经新闻分析师。请分析今日全部财经新闻，输出结构化日报。

持仓标的：
{holdings}

关注领域：美联储、黄金、半导体/AI、人民币、中国宏观政策、行业政策（电网/有色）、地缘政治、日本央行

原始新闻：
{news_list}

请输出：
# {date} 每日财经日报

## 🔴 必看（直接影响持仓）
每条包含：标题/摘要、影响分析、关联标的、情绪方向（多/空/中性）

## 🟡 重要（影响策略方向）
每条包含：标题/摘要、简要说明、情绪方向

## 🔵 参考
标题/摘要列表

过滤规则：
- 去除：个股减持公告、行政处罚、监管函、问询函、股东大会通知等噪音
- 去除：重复新闻
- 保留：所有与持仓标的和关注领域相关的新闻，无论重要程度"""
