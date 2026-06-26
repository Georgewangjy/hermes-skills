#!/usr/bin/env python3
"""quote-lookup: A股/ETF/场外基金报价查询。

用法:
    python quote.py 600519
    python quote.py 沪深300
    python quote.py 000300,510300,012414
    python quote.py 012414 --market fund
    python quote.py --refresh-cache
"""

import argparse
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.join(SCRIPT_DIR, "..")
CONFIG_PATH = os.path.join(SKILL_DIR, "config.json")
CODE_MAP_PATH = os.path.join(SKILL_DIR, "knowledge_base", "code_map.json")
CACHE_DIR = os.path.join(SKILL_DIR, "knowledge_base")

# ============================================================================
# 配置加载
# ============================================================================


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_code_map() -> dict:
    with open(CODE_MAP_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_code_map(data: dict) -> None:
    data["updated"] = datetime.now().strftime("%Y-%m-%d")
    with open(CODE_MAP_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ============================================================================
# 网络工具
# ============================================================================


def build_retry_session(retries: int = 3, backoff: float = 0.5) -> requests.Session:
    session = requests.Session()
    retry = Retry(total=retries, backoff_factor=backoff,
                  status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


SESSION = build_retry_session()

# ============================================================================
# 代码→类型识别
# ============================================================================


def detect_type(code: str) -> str:
    """识别标的类型: stock / etf / index / fund。

    规则:
        - A股: 000001-002999, 300001-301999, 600000-689999
        - 上交所ETF: 510/511/512/513/515/516/518xxx
        - 深交所ETF: 159xxx
        - 深市指数: 399xxx
        - 沪市指数: 000xxx (6位)
        - 0开头其他6位: stock_or_fund (歧义，先查场内再降级场外)
        - 其余非上述范围6位: fund
    """
    if not code or len(code) != 6 or not code.isdigit():
        return "unknown"

    prefix3 = code[:3]

    # ETF
    if prefix3 in ("159", "510", "511", "512", "513", "515", "516", "518"):
        return "etf"

    # A股
    if code[0] in ("6", "9"):
        return "stock"
    if code[0] == "3":
        if prefix3 == "399":
            return "index"
        return "stock"
    if prefix3 in ("001", "002"):
        return "stock"

    # 0开头: 沪市指数000xxx / 深市股票 / 场外基金
    if prefix3 == "000":
        return "index"

    # 0开头其他: 歧义
    if code[0] == "0":
        return "stock_or_fund"

    # 其余非上述范围6位: 场外基金
    return "fund"


def is_on_market_type(detected_type: str) -> bool:
    """是否为场内标的（有实时行情）。"""
    return detected_type in ("stock", "etf", "index", "stock_or_fund")


# ============================================================================
# 名称→代码解析
# ============================================================================


def parse_input(input_str: str) -> str:
    """解析输入: 纯数字/sh前缀/中文名称 → 6位代码或原名。"""
    s = input_str.strip()
    if not s:
        return s

    # sh/sz前缀 → 去前缀
    if s.lower().startswith(("sh", "sz")) and len(s) == 8 and s[2:].isdigit():
        return s[2:]

    # 纯6位数字 → 直接返回
    if len(s) == 6 and s.isdigit():
        return s

    # 可能是纯数字但非6位（如5位代码）也直接返回
    if s.isdigit():
        return s

    # 中文名称 → 需查映射
    return s


def resolve_name(name: str, code_map: dict, config: dict) -> dict:
    """将中文名称解析为代码。

    Returns:
        dict: {"code": "000300"} 或 {"error": "multiple_match", ...} 或 {"error": "not_found", ...}
    """
    # 第1层: code_map index
    index = code_map.get("index", {})
    if name in index:
        return {"code": index[name]}

    # 第2层: akshare 本地缓存索引
    candidates = search_akshare_cache(name, code_map, config)

    if not candidates:
        return {"error": "not_found", "input": name}

    if len(candidates) == 1:
        code = candidates[0]["code"]
        # 只自动追加指数/ETF到index
        det = detect_type(code)
        if det in ("index", "etf"):
            code_map.setdefault("index", {})[name] = code
            save_code_map(code_map)
        return {"code": code}

    return {"error": "multiple_match", "input": name, "candidates": candidates}


def search_akshare_cache(name: str, code_map: dict, _config: dict) -> list[dict]:
    """在 akshare 缓存索引中模糊搜索。"""
    candidates = []

    # 搜索股票/ETF/指数缓存
    stock_cache = code_map.get("akshare_cache", {}).get("stock_data_path")
    if stock_cache and os.path.exists(stock_cache):
        candidates.extend(_search_csv(name, stock_cache))

    # 搜索基金缓存
    fund_cache = code_map.get("akshare_cache", {}).get("fund_data_path")
    if fund_cache and os.path.exists(fund_cache):
        candidates.extend(_search_csv(name, fund_cache))

    return candidates


def _search_csv(name: str, csv_path: str) -> list[dict]:
    """在CSV文件中搜索包含名称的记录。"""
    import csv  # pylint: disable=import-outside-toplevel
    results = []
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row_name = row.get("名称", "")
                row_code = row.get("代码", "")
                if name in row_name and row_code:
                    results.append({
                        "code": row_code,
                        "name": row_name,
                        "type": detect_type(row_code),
                    })
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.warning("搜索缓存 %s 失败: %s", csv_path, e)
    return results


# ============================================================================
# akshare 缓存管理
# ============================================================================


def refresh_akshare_cache(code_map: dict, config: dict, force: bool = False) -> dict:
    """akshare 缓存已禁用。"""
    return code_map
    ttl_hours = config.get("akshare_cache_ttl_hours", 24)
    now = datetime.now()

    # 股票缓存
    stock_updated = cache_info.get("stock_updated")
    stock_last_attempt = cache_info.get("stock_last_attempt")
    need_stock = (force
                  or (not _is_recent_attempt(stock_last_attempt, minutes=30)
                      and (not stock_updated
                           or _is_expired(stock_updated, now, ttl_hours))))
    if need_stock:
        cache_info["stock_last_attempt"] = now.isoformat()
        try:
            logger.info("刷新 akshare 股票名称缓存...")
            df = ak.stock_zh_a_spot_em()
            stock_path = os.path.join(CACHE_DIR, "akshare_stocks.csv")
            df[["代码", "名称"]].to_csv(stock_path, index=False, encoding="utf-8")
            cache_info["stock_updated"] = now.isoformat()
            cache_info["stock_data_path"] = stock_path
            logger.info("股票缓存已刷新，共 %d 条", len(df))
            time.sleep(2)  # 避免限流
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.warning("刷新股票缓存失败: %s", e)

    # 基金缓存
    fund_updated = cache_info.get("fund_updated")
    fund_last_attempt = cache_info.get("fund_last_attempt")
    need_fund = (force
                 or (not _is_recent_attempt(fund_last_attempt, minutes=30)
                     and (not fund_updated
                          or _is_expired(fund_updated, now, ttl_hours))))
    if need_fund:
        cache_info["fund_last_attempt"] = now.isoformat()
        try:
            logger.info("刷新 akshare 基金名称缓存...")
            df = ak.fund_name_em()
            fund_path = os.path.join(CACHE_DIR, "akshare_funds.csv")
            df[["基金代码", "基金简称"]].rename(
                columns={"基金简称": "名称", "基金代码": "代码"}
            ).to_csv(fund_path, index=False, encoding="utf-8")
            cache_info["fund_updated"] = now.isoformat()
            cache_info["fund_data_path"] = fund_path
            logger.info("基金缓存已刷新，共 %d 条", len(df))
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.warning("刷新基金缓存失败: %s，保留旧缓存", e)

    code_map["akshare_cache"] = cache_info
    save_code_map(code_map)
    return code_map


def _is_expired(updated_str: str, now: datetime, ttl_hours: int) -> bool:
    """检查缓存是否过期。"""
    try:
        updated_time = datetime.fromisoformat(updated_str)
        return (now - updated_time) > timedelta(hours=ttl_hours)
    except (ValueError, TypeError):
        return True


def _is_recent_attempt(attempt_str: str, minutes: int = 30) -> bool:
    """检查上次尝试是否在指定分钟内，避免失败后反复重试。"""
    if not attempt_str:
        return False
    try:
        attempt_time = datetime.fromisoformat(attempt_str)
        return (datetime.now() - attempt_time) < timedelta(minutes=minutes)
    except (ValueError, TypeError):
        return False


# ============================================================================
# 数据源: 新浪财经
# ============================================================================

SINA_FIELD_MAP = {
    0: "name", 1: "open", 2: "prev_close", 3: "price",
    4: "high", 5: "low", 8: "volume", 9: "amount",
}


def build_sina_code(code: str) -> str:
    """统一代码 → 新浪格式 sh/sz + 6位代码。"""
    if code.startswith(("6", "9")):
        return f"sh{code}"
    det = detect_type(code)
    if det == "index" and code[:3] == "000":
        return f"sh{code}"
    if code[:3] in ("510", "511", "512", "513", "515", "516", "518"):
        return f"sh{code}"
    return f"sz{code}"


def fetch_sina(codes: list[str], config: dict) -> dict[str, dict]:
    """新浪批量获取实时行情。"""
    if not codes:
        return {}

    sources = config.get("sources", {}).get("sina", {})
    url = sources.get("url", "https://hq.sinajs.cn/list=")
    referer = sources.get("referer", "https://finance.sina.com.cn")
    encoding = sources.get("encoding", "gbk")
    timeout = config.get("timeout_seconds", 3)

    sina_codes = [build_sina_code(c) for c in codes]
    full_url = f"{url}{','.join(sina_codes)}"
    headers = {"Referer": referer}

    resp = SESSION.get(full_url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    resp.encoding = encoding

    return _parse_sina(resp.text, codes)


def _parse_sina(text: str, codes: list[str]) -> dict[str, dict]:
    """解析新浪返回的行情数据。"""
    results = {}
    for code in codes:
        sina_code = build_sina_code(code)
        pattern = rf'var hq_str_{sina_code}="([^"]*)";'
        match = re.search(pattern, text)
        if not match or not match.group(1).strip():
            results[code] = {"code": code, "error": "no_data", "source": "sina"}
            continue

        parts = match.group(1).split(",")
        if len(parts) < 10:
            results[code] = {"code": code, "error": "format_error", "source": "sina"}
            continue

        quote = {"code": code, "source": "sina"}
        for idx, field_name in SINA_FIELD_MAP.items():
            if idx >= len(parts) or not parts[idx].strip():
                quote[field_name] = None
                continue
            try:
                quote[field_name] = float(parts[idx].strip())
            except ValueError:
                quote[field_name] = parts[idx].strip()

        quote["name"] = parts[0].strip()
        _enrich_quote(quote)
        results[code] = quote

    return results


# ============================================================================
# 数据源: 腾讯财经
# ============================================================================

TENCENT_FIELD_MAP = {
    1: "name", 3: "price", 4: "prev_close", 5: "open",
    32: "change_pct", 33: "high", 34: "low",
    36: "volume", 37: "amount",
}


def build_tencent_code(code: str) -> str:
    """统一代码 → 腾讯格式（与新浪相同）。"""
    return build_sina_code(code)


def fetch_tencent(codes: list[str], config: dict) -> dict[str, dict]:
    """腾讯批量获取实时行情。"""
    if not codes:
        return {}

    sources = config.get("sources", {}).get("tencent", {})
    url = sources.get("url", "https://qt.gtimg.cn/q=")
    encoding = sources.get("encoding", "gbk")
    timeout = config.get("timeout_seconds", 3)

    tencent_codes = [build_tencent_code(c) for c in codes]
    full_url = f"{url}{','.join(tencent_codes)}"

    resp = SESSION.get(full_url, timeout=timeout)
    resp.raise_for_status()
    resp.encoding = encoding

    return _parse_tencent(resp.text, codes)


def _parse_tencent(text: str, codes: list[str]) -> dict[str, dict]:
    """解析腾讯返回的行情数据。"""
    results = {}
    for code in codes:
        tencent_code = build_tencent_code(code)
        pattern = rf'v_{tencent_code}="([^"]*)";'
        match = re.search(pattern, text)
        if not match or not match.group(1).strip():
            results[code] = {"code": code, "error": "no_data", "source": "tencent"}
            continue

        parts = match.group(1).split("~")
        if len(parts) < 30:
            results[code] = {"code": code, "error": "format_error", "source": "tencent"}
            continue

        quote = {"code": code, "source": "tencent"}
        for idx, field_name in TENCENT_FIELD_MAP.items():
            if idx >= len(parts) or not parts[idx].strip():
                quote[field_name] = None
                continue
            try:
                quote[field_name] = float(parts[idx].strip())
            except ValueError:
                quote[field_name] = parts[idx].strip()

        # 腾讯成交量单位为手、成交额单位为万，转换为股和元
        if quote.get("volume") is not None:
            quote["volume"] = quote["volume"] * 100
        if quote.get("amount") is not None:
            quote["amount"] = quote["amount"] * 10000

        _enrich_quote(quote)
        results[code] = quote

    return results


# ============================================================================
# 数据源: 天天基金（场外基金估值）
# ============================================================================


def fetch_fund_estimate(code: str, config: dict) -> dict:
    """天天基金获取场外基金估值。"""
    sources = config.get("sources", {}).get("eastmoney_fund", {})
    url_template = sources.get("url", "http://fundgz.1234567.com.cn/js/{code}.js")
    timeout = config.get("timeout_seconds", 3)

    url = url_template.format(code=code)
    resp = SESSION.get(url, timeout=timeout)
    resp.raise_for_status()

    match = re.search(r'jsonpgz\((.*)\)', resp.text)
    if not match:
        return {"code": code, "error": "format_error", "source": "eastmoney_fund"}

    data = json.loads(match.group(1))
    if not data or not data.get("gsz"):
        return {"code": code, "error": "no_data", "source": "eastmoney_fund"}

    return {
        "code": code,
        "name": data["name"],
        "type": "fund",
        "nav": float(data["dwjz"]),
        "nav_date": data.get("jzrq"),
        "estimate_nav": float(data["gsz"]),
        "estimate_change_pct": float(data["gszzl"]) if data.get("gszzl") else None,
        "estimate_time": data.get("gztime"),
        "source": "eastmoney_fund",
    }


def fetch_fund_acc_nav(code: str) -> Optional[float]:
    """akshare 累计净值查询已禁用。"""
    return None


# ============================================================================
# 行情补充计算
# ============================================================================


def _enrich_quote(quote: dict) -> None:
    """补充涨跌幅、涨跌额、振幅、收盘标志。"""
    price = quote.get("price")
    prev_close = quote.get("prev_close")

    # 收盘判断
    is_closed = (price is None or price <= 0) and prev_close and prev_close > 0
    if is_closed and prev_close:
        quote["price"] = prev_close
    quote["is_closed"] = is_closed

    # 涨跌幅
    if quote.get("price") and prev_close and prev_close > 0:
        if quote.get("change_pct") is None:
            quote["change_pct"] = round((quote["price"] - prev_close) / prev_close * 100, 2)
        # 涨跌额
        quote["change_amt"] = round(quote["price"] - prev_close, 2)
    else:
        quote["change_pct"] = quote.get("change_pct")
        quote["change_amt"] = None

    # 振幅
    high = quote.get("high")
    low = quote.get("low")
    if high and low and prev_close and prev_close > 0 and not is_closed:
        quote["amplitude"] = round((high - low) / prev_close * 100, 2)
    else:
        quote["amplitude"] = None


# ============================================================================
# 限流 & 容错: 数据源冷却管理
# ============================================================================


class SourceCooldown:
    """数据源冷却状态管理（内存级，脚本退出即重置）。"""

    def __init__(self, config: dict):
        rl = config.get("rate_limit", {})
        self.cooldown_seconds = rl.get("source_cooldown_seconds", 600)
        self.fail_threshold = rl.get("source_fail_threshold", 5)
        self.retry_delays = rl.get("retry_delays", [1, 2])
        self._fail_counts: dict[str, int] = {}
        self._cooldown_until: dict[str, float] = {}

    def is_cooled_down(self, source: str) -> bool:
        """数据源是否在冷却期。"""
        until = self._cooldown_until.get(source, 0)
        if time.time() < until:
            return True
        # 冷却期已过，清除冷却标记（失败计数保留，由 record_success 重置）
        self._cooldown_until.pop(source, None)
        return False

    def record_failure(self, source: str) -> None:
        """记录一次失败，超过阈值则进入冷却。"""
        count = self._fail_counts.get(source, 0) + 1
        self._fail_counts[source] = count
        if count >= self.fail_threshold:
            self._cooldown_until[source] = time.time() + self.cooldown_seconds
            logger.warning("数据源 %s 连续失败 %d 次，进入冷却 %d 秒",
                           source, count, self.cooldown_seconds)

    def record_success(self, source: str) -> None:
        """成功则重置失败计数。"""
        self._fail_counts.pop(source, None)


# ============================================================================
# 主逻辑: 报价查询
# ============================================================================


def fetch_on_market(codes: list[str], config: dict,
                    cooldown: SourceCooldown) -> dict[str, dict]:
    """场内标的查询: 新浪 → 腾讯，带限流容错。"""
    results = {}
    remaining = codes[:]

    # 新浪
    if remaining and not cooldown.is_cooled_down("sina"):
        try:
            logger.info("新浪获取: %s", remaining)
            sina_results = fetch_sina(remaining, config)
            succeeded = [c for c, q in sina_results.items() if "error" not in q]
            failed = [c for c, q in sina_results.items() if "error" in q]

            for code in succeeded:
                results[code] = sina_results[code]
            remaining = [c for c in remaining if c not in succeeded]

            # 批量缺项 → 单独重试1次
            if failed:
                logger.info("新浪缺项重试: %s", failed)
                try:
                    retry_results = fetch_sina(failed, config)
                    for code, q in retry_results.items():
                        if "error" not in q:
                            results[code] = q
                            remaining.remove(code)
                except Exception as e:  # pylint: disable=broad-exception-caught
                    logger.warning("新浪重试失败: %s", e)

            cooldown.record_success("sina")
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.warning("新浪数据源异常: %s", e)
            cooldown.record_failure("sina")
            # 指数退避重试
            for delay in cooldown.retry_delays:
                if cooldown.is_cooled_down("sina"):
                    break
                time.sleep(delay)
                try:
                    retry = fetch_sina(remaining, config)
                    for code, q in retry.items():
                        if "error" not in q:
                            results[code] = q
                    remaining = [c for c in remaining if c not in results]
                    cooldown.record_success("sina")
                    break
                except Exception:  # pylint: disable=broad-exception-caught
                    cooldown.record_failure("sina")

    # 腾讯
    if remaining and not cooldown.is_cooled_down("tencent"):
        try:
            logger.info("腾讯获取: %s", remaining)
            tencent_results = fetch_tencent(remaining, config)
            succeeded = [c for c, q in tencent_results.items() if "error" not in q]
            failed = [c for c, q in tencent_results.items() if "error" in q]

            for code in succeeded:
                results[code] = tencent_results[code]
            remaining = [c for c in remaining if c not in succeeded]

            # 批量缺项 → 单独重试1次
            if failed:
                logger.info("腾讯缺项重试: %s", failed)
                try:
                    retry_results = fetch_tencent(failed, config)
                    for code, q in retry_results.items():
                        if "error" not in q:
                            results[code] = q
                            remaining.remove(code)
                except Exception as e:  # pylint: disable=broad-exception-caught
                    logger.warning("腾讯重试失败: %s", e)

            cooldown.record_success("tencent")
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.warning("腾讯数据源异常: %s", e)
            cooldown.record_failure("tencent")
            for delay in cooldown.retry_delays:
                if cooldown.is_cooled_down("tencent"):
                    break
                time.sleep(delay)
                try:
                    retry = fetch_tencent(remaining, config)
                    for code, q in retry.items():
                        if "error" not in q:
                            results[code] = q
                    remaining = [c for c in remaining if c not in results]
                    cooldown.record_success("tencent")
                    break
                except Exception:  # pylint: disable=broad-exception-caught
                    cooldown.record_failure("tencent")

    # 标记失败
    for code in remaining:
        results[code] = {"code": code, "error": "all_sources_failed"}

    return results


def fetch_off_market(code: str, config: dict) -> dict:
    """场外基金查询: 天天基金估值 + akshare累计净值。"""
    fund_interval = config.get("rate_limit", {}).get("fund_request_interval", 0.5)

    # 天天基金估值
    try:
        quote = fetch_fund_estimate(code, config)
        if "error" not in quote:
            # 补充累计净值
            acc_nav = fetch_fund_acc_nav(code)
            if acc_nav is not None:
                quote["acc_nav"] = acc_nav
                quote["source"] = "eastmoney_fund"
            time.sleep(fund_interval)
            return quote
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.warning("天天基金获取 %s 失败: %s", code, e)

    return {"code": code, "error": "all_sources_failed"}


# ============================================================================
# 名称歧义处理: stock_or_fund
# ============================================================================


def resolve_ambiguous(code: str, config: dict,
                      cooldown: SourceCooldown) -> dict:
    """0开头歧义代码: 先查场内，失败再查场外基金。"""
    # 先当场内查
    result = fetch_on_market([code], config, cooldown)
    if code in result and "error" not in result[code]:
        return result[code]

    # 场内失败 → 当场外基金
    fund_result = fetch_off_market(code, config)
    if "error" not in fund_result:
        return fund_result

    return {"code": code, "error": "all_sources_failed"}


# ============================================================================
# 主入口
# ============================================================================


def run_query(codes_input: str, market: Optional[str] = None,
              refresh_cache: bool = False) -> dict:
    """执行报价查询，返回结果dict。"""
    config = load_config()
    code_map = load_code_map()

    # 刷新缓存
    code_map = refresh_akshare_cache(code_map, config, force=refresh_cache)

    # 解析输入
    raw_items = [s.strip() for s in codes_input.split(",") if s.strip()]
    if not raw_items:
        return {"error": "no_input"}

    # 批量上限
    if len(raw_items) > config.get("batch_limit", 20):
        return {"error": "batch_limit_exceeded", "limit": config.get("batch_limit", 20)}

    # 第1步: 名称→代码解析
    resolved_codes = []
    for item in raw_items:
        parsed = parse_input(item)
        if len(parsed) == 6 and parsed.isdigit():
            resolved_codes.append(parsed)
        else:
            # 中文名称
            name_result = resolve_name(parsed, code_map, config)
            if "code" in name_result:
                resolved_codes.append(name_result["code"])
            else:
                # 多匹配或未找到，直接返回该结果
                return name_result

    # 第2步: 按类型分组
    cooldown = SourceCooldown(config)
    on_market_codes = []
    off_market_codes = []
    ambiguous_codes = []

    for code in resolved_codes:
        if market == "fund":
            det = "fund"
        else:
            det = detect_type(code)

        if det == "stock_or_fund":
            ambiguous_codes.append(code)
        elif det == "fund" or (market == "fund" and det != "fund"):
            off_market_codes.append(code)
        elif is_on_market_type(det):
            on_market_codes.append(code)
        else:
            off_market_codes.append(code)

    # 第3步: 数据获取
    results = {}

    # 场内
    if on_market_codes:
        on_results = fetch_on_market(on_market_codes, config, cooldown)
        results.update(on_results)

    # 歧义代码
    for code in ambiguous_codes:
        results[code] = resolve_ambiguous(code, config, cooldown)

    # 场外
    for code in off_market_codes:
        results[code] = fetch_off_market(code, config)

    # 第4步: 补充type字段
    for code, quote in results.items():
        if "error" not in quote and "type" not in quote:
            quote["type"] = detect_type(code)

    return results


def main():
    parser = argparse.ArgumentParser(description="quote-lookup: A股/ETF/场外基金报价查询")
    parser.add_argument("codes", nargs="?", help="标的代码或名称，多个用逗号分隔")
    parser.add_argument("--market", choices=["stock", "fund"],
                        help="指定市场: stock/fund，自动识别时可省略")
    parser.add_argument("--refresh-cache", action="store_true",
                        help="强制刷新akshare名称索引缓存")
    args = parser.parse_args()

    if not args.codes and not args.refresh_cache:
        parser.error("必须提供标的代码或名称，或使用 --refresh-cache")

    if args.refresh_cache and not args.codes:
        config = load_config()
        code_map = load_code_map()
        refresh_akshare_cache(code_map, config, force=True)
        print(json.dumps({"status": "cache_refreshed"}, ensure_ascii=False))
        return

    results = run_query(args.codes, market=args.market,
                        refresh_cache=args.refresh_cache)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
