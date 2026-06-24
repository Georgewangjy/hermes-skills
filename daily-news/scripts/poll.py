#!/usr/bin/env python3
"""daily-news 模式1：实时轮询快兰斯，判断即时推送。"""

import argparse
import json
import logging
from datetime import datetime

from common import (
    load_config, load_state, save_state,
    fetch_kualansi, check_instant_alert, is_quiet_hours,
    is_emergency_keyword, append_raw_news, append_alert,
    call_ai, build_holdings_text, PROMPT_INSTANT, send_feishu,
)

logger = logging.getLogger(__name__)


def poll(pages: int = 1) -> dict:
    """执行一次轮询。返回统计信息。"""
    config = load_config()
    state = load_state()
    last_ts = state.get("last_timestamp", "")
    holdings_text = build_holdings_text(config)

    new_items = []
    latest_ts = last_ts
    url = None

    for _ in range(pages):
        data = fetch_kualansi(url, config)
        items = data.get("list", [])
        if not items:
            break

        for item in items:
            item_time = item.get("time", "")
            # 跳过已处理过的
            if item_time and item_time <= last_ts:
                continue
            new_items.append(item)
            if item_time > latest_ts:
                latest_ts = item_time

        # 下一页
        next_page = data.get("nextpage", "")
        if not next_page:
            break
        url = next_page

    stats = {"total_fetched": 0, "new_count": 0, "alerts": 0}

    if not new_items:
        logger.info("无新内容")
        return stats

    # 按时间排序（旧→新）
    new_items.sort(key=lambda x: x.get("time", ""))
    stats["total_fetched"] = len(new_items)

    # 追加到原始快讯文件
    date_str = datetime.now().strftime("%Y-%m-%d")
    added = append_raw_news(new_items, config, date_str)
    stats["new_count"] = added

    # 检查即时推送
    for item in new_items:
        content = item.get("content", "")
        level = str(item.get("Level", "0"))
        item_time = item.get("time", "")

        if check_instant_alert(content, level, config):
            # 调AI做即时分析
            prompt = PROMPT_INSTANT.format(content=content, holdings=holdings_text)
            ai_result = call_ai(prompt, config)

            # 格式化推送内容
            alert_text = f"🔴 [{item_time[-8:]}] {content[:60]}\n{ai_result}"
            append_alert(alert_text, config, date_str)
            stats["alerts"] += 1

            # 飞书推送判断
            should_push = True
            if is_quiet_hours(config):
                if is_emergency_keyword(content, config):
                    should_push = True
                else:
                    should_push = False

            if should_push:
                send_feishu(alert_text, config)

    # 更新状态
    if latest_ts > last_ts:
        state["last_timestamp"] = latest_ts
        save_state(state)

    logger.info("轮询完成: 新增%d条, 即时推送%d条", stats["new_count"], stats["alerts"])
    return stats


def main():
    parser = argparse.ArgumentParser(description="daily-news: 实时轮询快兰斯")
    parser.add_argument("--pages", type=int, default=1, help="拉取页数（默认1）")
    args = parser.parse_args()

    stats = poll(pages=args.pages)
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
