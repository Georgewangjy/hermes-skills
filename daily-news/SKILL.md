---
name: daily-news
description: 每日财经新闻抓取+AI分析，实时轮询快兰斯快讯+每日日报生成
triggers:
  - 新闻
  - 日报
  - daily news
parameters:
  - name: mode
    description: 运行模式：poll（实时轮询）/ daily（每日日报），默认 poll
    required: false
  - name: pages
    description: 轮询模式拉取页数，默认1（仅最新页）
    required: false
---

# 每日财经新闻

## 执行步骤

### 模式1：实时轮询（poll）

1. 读取 `config.json` 获取数据源和关键词配置。
2. 读取 `state.json` 获取上次最新时间戳。
3. 拉取快兰斯第1页（20条）。
4. 对比时间戳，无新内容 → 结束。
5. 有新内容 →
   a. 新条目追加写入当日原始快讯文件（`YYYY-MM-DD_raw.json`）。
   b. 检查即时推送条件：Level=2 且关键词命中。
      → 命中：调AI做单条分析 + 输出飞书推送格式到 `YYYY-MM-DD_alerts.md`。
      → 未命中：仅存文件。
6. 更新 `state.json` 时间戳。

### 模式2：每日日报（daily）

1. 拉取快兰斯昨日0:00→今日8:00的全部新闻（翻页直到时间超范围）。
2. 补充抓取金十数据当前页面内容。
3. 合并去重。
4. 调AI（Kimi K2.7）做完整分析，输出结构化日报MD。
5. 日报写入 `YYYY-MM-DD_daily.md`。

## 数据源

| 优先级 | 数据源 | 用途 | 说明 |
|--------|--------|------|------|
| 1 | 快兰斯财经直播 | 实时快讯 | HTTP API，UTF-8 BOM编码，每页20条 |
| 2 | 金十数据 | 日报补充 | 仅日报模式使用，侧重美联储/全球宏观 |

## AI分析

- **模型**: Kimi K2.7（Moonshot官方API）
- **分析3件事**: 去噪、结构化摘要、持仓关联分析
- **即时分析**: 单条/少量新闻，快速判断影响
- **日报分析**: 批量新闻，输出🔴必看/🟡重要/🔵参考三级结构

## 即时推送关键词

暴跌|熔断|加息|降息|降准|战争|黄金突破|人民币暴涨|人民币暴跌|台海|半导体禁令|制裁|紧急|突发|重大

## 文件输出

| 文件 | 路径 | 说明 |
|------|------|------|
| 原始快讯 | `data/wiki/main/sources/news/YYYY-MM-DD_raw.json` | 快兰斯原始JSON（追加写入） |
| AI日报 | `data/wiki/main/sources/news/YYYY-MM-DD_daily.md` | AI分析后的日报MD |
| 即时推送记录 | `data/wiki/main/sources/news/YYYY-MM-DD_alerts.md` | 即时推送内容备份 |
| 轮询状态 | `skills/daily-news/state.json` | 上次抓取时间戳+最新newsid |

## 飞书推送

- 即时推送命中 + 日报中🔴必看项
- 安静时段：23:59-07:00不推送（除非极端事件）
- 推送接口预留，由OpenClaw调试对接

## 使用示例

```bash
# 实时轮询（单次）
python scripts/poll.py

# 每日日报
python scripts/daily.py

# 指定拉取页数
python scripts/poll.py --pages 3
```

## 依赖

- `openai>=1.0`：OpenAI兼容客户端（项目已有）
- 标准库：`urllib.request`, `json`, `re`, `datetime`
