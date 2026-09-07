"""得物海外开放平台 (POIZON / open.poizon.com) 价格查询客户端。

核心能力：输入货号（article number）→ 返回每个尺码的平台实时最低价。

数据流：
    货号  --[接口140 by-article-number]-->  globalSpuId + 各尺码 globalSkuId
    globalSkuId 列表  --[接口141 batchPrice]-->  每个 sku 的最低价

签名算法与国内 open.dewu.com 完全一致，已用官方文档示例逐字节验证。
文档：https://open.poizon.com/doc/list/documentationDetail/9
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Iterable

import requests

GATEWAY = "https://open.poizon.com"
ENV_FILE = Path(__file__).with_name(".env")

# 接口路径
PATH_BY_ARTICLE = "/dop/api/v1/pop/api/v1/intl-commodity/intl/sku/sku-basic-info/by-article-number"
PATH_BY_GLOBAL_SKU = "/dop/api/v1/pop/api/v1/intl-commodity/intl/sku/sku-basic-info/by-global-sku"
PATH_BATCH_PRICE = "/dop/api/v1/pop/api/v1/recommend-bid/batchPrice"
PATH_SINGLE_PRICE = "/dop/api/v1/pop/api/v1/recommend-bid/price"

# 统计数据（销量/最低价）只在 statisticsDataQry 显式打开时才返回
STAT_REGION = "US"   # by-global-sku 的统计口径固定用 US，CN 会报 region not found

# 出价类型：20=现货，25=寄售；销售类型：7=预售（沿用官方示例默认值）
DEFAULT_BIDDING_TYPE = 20
DEFAULT_SALE_TYPE = 7


def load_env() -> None:
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


# ---------------------------------------------------------------- 签名

_ALWAYS_SAFE = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.*")


def _java_url_encode(value: str) -> str:
    """对齐 Java URLEncoder.encode(s, "UTF-8")：空格->+，* 不编码，~->%7E。"""
    out = []
    for byte in value.encode("utf-8"):
        ch = chr(byte)
        if ch in _ALWAYS_SAFE:
            out.append(ch)
        elif ch == " ":
            out.append("+")
        else:
            out.append(f"%{byte:02X}")
    return "".join(out)


def _value_to_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return ",".join(
            json.dumps(v, ensure_ascii=False, separators=(",", ":")) if isinstance(v, (dict, list))
            else _value_to_string(v)
            for v in value
        )
    if isinstance(value, dict):
        # 注意：嵌套对象的 key 必须保持插入序，不能排序。
        # 官方 Java SDK 用 Jackson 序列化（保持插入序），排序会导致 401 签名认证失败。
        return json.dumps({k: v for k, v in value.items() if v is not None},
                          ensure_ascii=False, separators=(",", ":"))
    return str(value)


def create_sign(params: dict, app_secret: str) -> str:
    clean = {k: v for k, v in params.items() if k not in ("sign", "secret") and v is not None}
    pairs = [f"{_java_url_encode(k)}={_java_url_encode(_value_to_string(clean[k]))}" for k in sorted(clean)]
    return hashlib.md5(("&".join(pairs) + app_secret).encode("utf-8")).hexdigest().upper()


# ---------------------------------------------------------------- 网关调用

def call(path: str, biz: dict, *, access_token: str | None = None, retries: int = 4) -> dict:
    app_key = os.getenv("DEWU_INTL_APP_KEY", "")
    app_secret = os.getenv("DEWU_INTL_APP_SECRET", "")
    if not app_key or not app_secret:
        raise RuntimeError("缺少 DEWU_INTL_APP_KEY / DEWU_INTL_APP_SECRET，请检查 .env")

    params: dict[str, Any] = dict(biz)
    params["app_key"] = app_key
    params["timestamp"] = int(time.time() * 1000)
    if access_token:
        params["access_token"] = access_token
    params["sign"] = create_sign(params, app_secret)

    last_exc = None
    for attempt in range(retries):
        try:
            r = requests.post(f"{GATEWAY}{path}", json=params,
                              headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
                              timeout=25)
            try:
                return r.json()
            except ValueError:
                return {"code": r.status_code, "msg": r.text[:300]}
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            time.sleep(1.5 * (attempt + 1))
    return {"code": None, "msg": f"network error: {last_exc}"}


# ---------------------------------------------------------------- 业务封装

class DewuError(RuntimeError):
    pass


def _money(cents: Any) -> float | None:
    """接口返回的是『币种最小单位数值』(带小数币种即分)，除 100 得主单位。"""
    return round(cents / 100, 2) if isinstance(cents, (int, float)) else None


def _fetch_article(article_number: str, region: str, language: str) -> list:
    r = call(PATH_BY_ARTICLE,
             {"articleNumber": article_number, "region": region,
              "language": language, "buyStatusEnable": True})
    if r.get("code") != 200:
        raise DewuError(f"货号查询失败 code={r.get('code')} msg={r.get('msg')}")
    return r.get("data") or []


def get_skus_by_article(article_number: str, region: str = "CN", language: str = "en") -> dict:
    """接口140：货号 -> 商品信息 + 各尺码 globalSkuId。

    货号字母区分大小写；原样查不到时自动用大写重试一次。
    """
    data = _fetch_article(article_number, region, language)
    if not data and article_number != article_number.upper():
        data = _fetch_article(article_number.upper(), region, language)
    if not data:
        return {}
    d = data[0]
    spu = d.get("spuInfo", {})
    skus = []
    for s in d.get("skuInfoList", []):
        props = {p.get("name"): p.get("value") for p in (s.get("regionSalePvInfoList") or [])}
        size = props.get("尺码") or props.get("Size") or props.get("size") \
            or (list(props.values())[-1] if props else None)
        skus.append({"size": size, "globalSkuId": s.get("globalSkuId"),
                     "skuId": s.get("dwSkuId"), "props": props})
    return {
        "articleNumber": spu.get("articleNumber", article_number),
        "title": spu.get("title"),
        "globalSpuId": d.get("globalSpuId"),
        "dwSpuId": spu.get("dwSpuId"),
        "category": spu.get("level1CategoryName"),
        "region": d.get("region", region),
        "skus": skus,
    }


def batch_price(global_sku_ids: Iterable[int], region: str = "CN", currency: str = "CNY",
                country_code: str | None = None,
                bidding_type: int = DEFAULT_BIDDING_TYPE,
                sale_type: int = DEFAULT_SALE_TYPE) -> dict[int, dict]:
    """接口141：一批 globalSkuId (<=20) -> 每个 sku 的最低价。返回 {globalSkuId: priceInfo}。"""
    ids = [int(i) for i in global_sku_ids if i]
    result: dict[int, dict] = {}
    for i in range(0, len(ids), 20):
        chunk = ids[i:i + 20]
        r = call(PATH_BATCH_PRICE,
                 {"globalSkuIdList": chunk, "region": region, "currency": currency,
                  "countryCode": country_code or region,
                  "biddingType": bidding_type, "saleType": sale_type})
        if r.get("code") != 200:
            raise DewuError(f"批量价格失败 code={r.get('code')} msg={r.get('msg')} "
                            f"err={(r.get('errors') or [{}])[0].get('message','')}")
        for item in (r.get("data") or []):
            leaks = item.get("leakInfos") or []
            result[item.get("globalSkuId")] = {
                "globalMinPrice": _money(item.get("globalMinPrice")),
                "asiaMinPrice": _money(item.get("asiaMinPrice")),
                "localMinPrice": _money(item.get("localMinPrice")),
                "usMinPrice": _money(item.get("usMinPrice")),
                "fen95ReferencePrice": _money(item.get("fen95ReferencePrice")),
                "otherPlatformMinPrice": _money(item.get("otherPlatformMinPrice")),
                "leakPrice": _money(leaks[0]["leakPrice"]) if leaks else None,
                "leakBuyerRegion": leaks[0].get("buyerRegion") if leaks else None,
            }
    return result


# 商品目录（接口140）只在部分区上架，US 覆盖最全；价格（接口141）再按目标区查。
CATALOG_REGION = "US"


def query_article(article_number: str, region: str = "CN", currency: str = "CNY",
                  country_code: str | None = None) -> dict:
    """一站式：货号 -> 商品信息 + 每个尺码的最低价。

    目录用 CATALOG_REGION 拉（US 覆盖最全），价格按 region/currency 查。
    """
    info = get_skus_by_article(article_number, region=CATALOG_REGION)
    if not info:
        return {"articleNumber": article_number, "found": False, "region": region,
                "country": (country_code or region), "currency": currency, "sizes": []}
    prices = batch_price([s["globalSkuId"] for s in info["skus"]],
                         region=region, currency=currency, country_code=country_code)
    info["region"] = region
    sizes = []
    for s in info["skus"]:
        p = prices.get(s["globalSkuId"], {})
        sizes.append({"size": s["size"], "globalSkuId": s["globalSkuId"], **p})
    info["found"] = True
    info["country"] = (country_code or region)
    info["currency"] = currency
    info["sizes"] = sizes
    del info["skus"]
    return info


def query_articles(article_numbers: Iterable[str], region: str = "CN", currency: str = "CNY",
                   country_code: str | None = None) -> list[dict]:
    """多货号批量查询。"""
    return [query_article(a.strip(), region=region, currency=currency, country_code=country_code)
            for a in article_numbers if a and a.strip()]


# ---------------------------------------------------------------- 销量

def batch_sales(global_sku_ids: Iterable[int]) -> dict[int, dict]:
    """[接口159] 一批 globalSkuId -> 每个 sku 的 30 天销量。返回 {globalSkuId: salesInfo}。

    必须打开 statisticsDataQry.salesEnable，否则销量字段一律为 null。
    """
    ids = [int(i) for i in global_sku_ids if i]
    if not ids:
        return {}
    r = call(PATH_BY_GLOBAL_SKU, {
        "globalSkuIds": ids,
        "region": STAT_REGION,
        "language": "en",
        "buyStatusEnable": True,
        "statisticsDataQry": {"salesEnable": True, "minPriceEnable": True},
    })
    if r.get("code") != 200:
        raise DewuError(f"销量查询失败 code={r.get('code')} msg={r.get('msg')}")

    result: dict[int, dict] = {}
    for row in (r.get("data") or []):
        for sku in row.get("skuInfoList", []):
            cs = sku.get("commoditySales") or {}
            result[sku.get("globalSkuId")] = {
                "globalSoldNum30": cs.get("globalSoldNum30"),
                "localSoldNum30": cs.get("localSoldNum30"),
                "globalMonthToMonthRatio": cs.get("globalMonthToMonthRatio"),
                "localMonthToMonthRatio": cs.get("localMonthToMonthRatio"),
            }
    return result


def query_articles_sales(article_numbers: Iterable[str]) -> list[dict]:
    """多货号批量查询销量。"""
    return [query_article_sales(a.strip()) for a in article_numbers if a and a.strip()]


def query_articles_full(article_numbers: Iterable[str], region: str = "CN", currency: str = "CNY",
                        country_code: str | None = None) -> list[dict]:
    """多货号批量查询『价格 + 销量』。"""
    return [query_article_full(a.strip(), region=region, currency=currency,
                               country_code=country_code)
            for a in article_numbers if a and a.strip()]


def query_article_sales(article_number: str) -> dict:
    """一站式：货号 -> 每个尺码的 30 天销量。"""
    info = get_skus_by_article(article_number, region=CATALOG_REGION)
    if not info:
        return {"articleNumber": article_number, "found": False, "sizes": []}
    sales = batch_sales([s["globalSkuId"] for s in info["skus"]])
    sizes = [{"size": s["size"], "globalSkuId": s["globalSkuId"],
              **sales.get(s["globalSkuId"], {})} for s in info["skus"]]
    info["found"] = True
    info["totalSoldNum30"] = sum(x.get("globalSoldNum30") or 0 for x in sizes)
    info["sizes"] = sizes
    del info["skus"]
    return info


# ---------------------------------------------------------------- 价格 + 销量

def query_article_full(article_number: str, region: str = "CN", currency: str = "CNY",
                       country_code: str | None = None) -> dict:
    """一站式：货号 -> 每个尺码的『价格 + 销量』。"""
    info = get_skus_by_article(article_number, region=CATALOG_REGION)
    if not info:
        return {"articleNumber": article_number, "found": False, "region": region,
                "country": (country_code or region), "currency": currency, "sizes": []}

    ids = [s["globalSkuId"] for s in info["skus"]]
    prices = batch_price(ids, region=region, currency=currency, country_code=country_code)
    try:
        sales = batch_sales(ids)
    except DewuError:
        sales = {}

    sizes = []
    for s in info["skus"]:
        gid = s["globalSkuId"]
        sizes.append({"size": s["size"], "globalSkuId": gid,
                      **prices.get(gid, {}), **sales.get(gid, {})})
    info["found"] = True
    info["country"] = (country_code or region)
    info["currency"] = currency
    info["region"] = region
    info["totalSoldNum30"] = sum(x.get("globalSoldNum30") or 0 for x in sizes)
    info["sizes"] = sizes
    del info["skus"]
    return info
