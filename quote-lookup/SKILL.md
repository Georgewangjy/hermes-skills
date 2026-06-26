---
name: quote-lookup
description: 查询A股、ETF、场外基金的实时/延迟报价与基金净值估值
triggers:
  - 报价查询
  - 查报价
  - quote lookup
parameters:
  - name: code
    description: 标的代码或名称，支持批量（逗号分隔），如 600519 或 沪深300 或 000300,510300,012414
    required: true
  - name: market
    description: 市场：stock / fund，自动识别时可省略
    required: false
---

# 报价查询

## 执行步骤

1. 读取 `config.json` 获取数据源配置和限流策略。
2. 解析输入代码/名称：
   - 纯6位数字 → 直接使用
   - sh/sz前缀 → 去前缀
   - 中文名称 → 查 `code_map.json` index，未命中查 akshare 缓存索引
3. 代码→类型自动识别：A股 / ETF / 指数 / 场外基金 / 歧义（先场内后场外）。
4. 数据获取：
   - **场内标的**：新浪（主）→ 腾讯（备用），3秒超时切换
   - **场外基金**：天天基金估值 + akshare 累计净值
5. 补充计算：涨跌额、振幅（非交易时段标null）。
6. 输出 JSON 到 stdout。

## 代码格式

| 格式 | 示例 | 处理 |
|------|------|------|
| 6位数字 | 000300, 510300 | 直接使用 |
| 带市场前缀 | sh000300, sz159915 | 去前缀 |
| 中文名称 | 沪深300, 纳指100 | 映射查找 |
| 基金6位代码 | 012414 | 自动识别为场外基金 |
| 批量 | 000300,510300,012414 | 逗号分隔，最多20个 |

## 输出字段

### 股票/ETF/指数

| 字段 | 类型 | 说明 |
|------|------|------|
| code | str | 标的代码 |
| name | str | 标的名称 |
| type | str | stock / etf / index |
| price | float | 最新价 |
| change_pct | float | 涨跌幅(%) |
| change_amt | float | 涨跌额 |
| open | float | 今开 |
| prev_close | float | 昨收 |
| high | float | 最高 |
| low | float | 最低 |
| volume | float | 成交量(股) |
| amount | float | 成交额(元) |
| amplitude | float/null | 振幅(%)，非交易时段null |
| is_closed | bool | 是否已收盘 |
| source | str | 数据源 |

### 场外基金

| 字段 | 类型 | 说明 |
|------|------|------|
| code | str | 基金代码 |
| name | str | 基金名称 |
| type | str | "fund" |
| nav | float | 最新净值 |
| nav_date | str | 净值日期 |
| estimate_nav | float | 估算净值 |
| estimate_change_pct | float | 估算涨跌幅(%) |
| acc_nav | float | 累计净值(akshare) |
| estimate_time | str | 估值时间 |
| source | str | 数据源 |

### 名称多匹配

| 字段 | 类型 | 说明 |
|------|------|------|
| error | str | "multiple_match" |
| input | str | 输入名称 |
| candidates | list | 候选列表 [{code, name, type}] |

## 数据源

| 优先级 | 数据源 | 用途 | 说明 |
|--------|--------|------|------|
| 1 | 新浪财经 | A股/ETF/指数实时 | 需Referer，支持批量 |
| 2 | 腾讯财经 | 备用实时 | 支持批量 |
| 3 | 天天基金 | 场外基金估值 | 单个查询 |
| 4 | akshare | 基金累计净值 + 名称索引 | 本地缓存24小时 |

## 限流与容错

- 场内批量缺项 → 单独重试1次
- 数据源连续失败5次 → 冷却10分钟
- 两个源都在冷却期 → 返回 all_sources_failed
- 场外基金请求间隔0.5秒
- akshare缓存刷新间隔2秒（先stock后fund），失败保留旧缓存

## 错误处理

| 场景 | 输出 |
|------|------|
| 代码不存在 | `{"code": "xxx", "error": "not_found"}` |
| 全部数据源失败 | `{"code": "xxx", "error": "all_sources_failed"}` |
| 批量部分失败 | 成功项正常 + 失败项标error |
| 超过20个 | `{"error": "batch_limit_exceeded", "limit": 20}` |
| 名称多匹配 | 返回候选列表 |
| 非交易时段 | is_closed=true, amplitude=null |

## 使用示例

```bash
python scripts/quote.py 600519
python scripts/quote.py 沪深300
python scripts/quote.py 000300,510300,012414
python scripts/quote.py 012414 --market fund
python scripts/quote.py --refresh-cache
```
