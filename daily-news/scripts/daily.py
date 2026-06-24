#!/usr/bin/env python3
"""daily-news 模式2：每日日报生成。"""

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta

from common import (
    load_config, fetch_kualansi_pages,
    deduplicate_news, filter_noise, append_raw_news, write_daily_report,
    call_ai, build_holdings_text, PROMPT_DAILY, send_feishu,
)

logger = logging.getLogger(__name__)


def generate_daily(target_date: str = None) -> str:
    """生成每日日报。返回日报内容。"""
    config = load_config()

    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")

    # 计算时间范围：昨日0:00 → 今日8:00
    dt = datetime.strptime(target_date, "%Y-%m-%d")
    start_time = (dt - timedelta(days=1)).strftime("%Y-%m-%d") + " 00:00:00"

    # 拉取快兰斯全部新闻
    logger.info("拉取快兰斯: %s → %s", start_time, target_date)
    kualansi_items = fetch_kualansi_pages(start_time, config)
    logger.info("快兰斯获取: %d条", len(kualansi_items))

    # 合并去重
    all_items = deduplicate_news(kualansi_items)

    if not all_items:
        logger.warning("无新闻数据")
        return ""

    # 追加原始快讯（全量，不过滤）
    append_raw_news(all_items, config, target_date)

    # AI分析前做噪音预筛选
    ai_items = filter_noise(all_items, config)

    # 按优先级排序：Level=2优先，然后按时间倒序
    ai_items.sort(key=lambda x: (str(x.get("Level", "0")) != "2", x.get("time", "")))

    # 限制发给AI的新闻条数，避免prompt过长
    max_items = 50
    if len(ai_items) > max_items:
        logger.info("新闻过多(%d条)，截取前%d条（Level=2优先）", len(ai_items), max_items)
        ai_items = ai_items[:max_items]

    # 构建新闻列表文本（每条截取前120字）
    news_list_parts = []
    for item in ai_items:
        time_str = item.get("time", "")
        content = item.get("content", "")[:120]
        level = item.get("Level", "0")
        marker = "🔴" if level == "2" else ""
        news_list_parts.append(f"[{time_str}] {marker}{content}")

    news_text = "\n".join(news_list_parts)

    # 调AI生成日报
    holdings_text = build_holdings_text(config)
    prompt = PROMPT_DAILY.format(
        holdings=holdings_text,
        news_list=news_text,
        date=target_date,
    )

    logger.info("调用AI生成日报...")
    report = call_ai(prompt, config)

    if not report:
        report = f"# {target_date} 每日财经日报\n\nAI分析返回为空，请重试。"
        write_daily_report(report, config, target_date)
        return report

    # 写入日报文件
    write_daily_report(report, config, target_date)

    # 推送🔴必看项摘要
    if "🔴" in report:
        # 提取🔴必看部分
        red_section = ""
        in_red = False
        for line in report.split("\n"):
            if line.startswith("## 🔴"):
                in_red = True
                continue
            if in_red and line.startswith("## "):
                break
            if in_red:
                red_section += line + "\n"

        if red_section.strip():
            summary = f"📊 {target_date} 日报必看项\n{red_section.strip()}"
            send_feishu(summary, config)

    logger.info("日报生成完成")
    return report


def main():
    parser = argparse.ArgumentParser(description="daily-news: 每日日报生成")
    parser.add_argument("--date", type=str, default=None,
                        help="目标日期 YYYY-MM-DD（默认今天）")
    args = parser.parse_args()

    report = generate_daily(target_date=args.date)
    if report:
        print(report)
    else:
        print(json.dumps({"error": "no_data"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
