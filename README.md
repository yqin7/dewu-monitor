# 得物海外价格查询 (dewu-monitor)

输入货号（article number），返回得物平台每个尺码的**实时最低价**。
数据来自得物海外开放平台 POIZON（`open.poizon.com`）。

```bash
python cli.py IJ7058
```
```
IJ7058  Adidas Adicolor Classics Firebird Track Jacket
  globalSpuId=10005355339  类目=Apparel  country=CN  currency=CNY
  尺码      globalSkuId   最低价           亚洲最低          漏出价
  XS      10626581818   CNY 525.00    CNY 525.00    CNY 550.00(CN)
  S       10626581819   CNY 405.00    CNY 405.00    CNY 405.00(CN)
  ...
```

---

## 快速开始

```bash
pip install -r requirements.txt

# 1) 命令行
python cli.py IJ7058                        # 单货号（默认 CN / CNY）
python cli.py IJ7058 206302-001             # 多货号
python cli.py IJ7058 --region US --currency USD --country-code US
python cli.py IJ7058 --json                 # JSON 输出

# 2) HTTP 接口
uvicorn api:app --reload --port 8000
#   GET  /price/IJ7058
#   GET  /price/IJ7058?region=US&currency=USD&country_code=US
#   POST /prices   body: {"articles":["IJ7058","206302-001"]}
```

凭证放在 `.env`（见 `.env.example`）：

```
DEWU_INTL_APP_KEY=生产 AppKey
DEWU_INTL_APP_SECRET=生产 AppSecret
```

---

## 查询价格的完整步骤（原理）

### 网关与鉴权
- **网关**：`https://open.poizon.com`，请求方式 POST，`Content-Type: application/json`。
- **无需 OAuth token**：价格与商品查询这几个接口 `needAuth` 虽标 true，但实测**只需应用签名即可调用**，不需要 access_token。（注意：调用 IP 必须在应用的 **IP 白名单** 内。）
- **签名 `sign`**：与国内 `open.dewu.com` 完全一致，算法见 `dewu_client.create_sign`：
  1. 移除 `sign`/`secret` 和所有 null 值参数；
  2. 加入 `app_key` 和 `timestamp`（毫秒）；
  3. 参数按 key 字典序排序；
  4. 每个 key、value 用 **Java 风格 URLEncode**（空格→`+`，`*` 不编码，`~`→`%7E`）；数组元素用逗号拼接；
  5. 拼成 `k1=v1&k2=v2...`，末尾直接追加 `app_secret`；
  6. MD5，转**大写**。
  （已用官方文档示例逐字节验证吻合。）

### 两步数据流

**第 1 步 · 货号 → globalSkuId**
接口 **[140]** `根据货号查询 Sku & Spu 基础信息`
`POST /dop/api/v1/pop/api/v1/intl-commodity/intl/sku/sku-basic-info/by-article-number`

| 入参 | 说明 |
|---|---|
| `articleNumber` | 货号，如 `IJ7058` |
| `region` | 目录区，用 **US**（覆盖最全；CN/HK/JP 等多数商品目录为空）|
| `language` | `en` |
| `buyStatusEnable` | `true` |

返回 `data[0].skuInfoList[*].globalSkuId`（每个尺码一个）+ `spuInfo.title` 等。

**第 2 步 · globalSkuId → 最低价**
接口 **[141]** `出价参考-批量`（一次最多 20 个）
`POST /dop/api/v1/pop/api/v1/recommend-bid/batchPrice`

| 入参 | 说明 |
|---|---|
| `globalSkuIdList` | globalSkuId 数组（≤20）|
| `region` | 价格区，如 `CN` |
| `currency` | 币种，如 `CNY` |
| `countryCode` | 国家码，如 `CN` |
| `biddingType` | **20=现货**，25=寄售（必填，缺了会报 `biddingType 为空或错误`）|
| `saleType` | 7=预售 |

返回数组，每项：`globalMinPrice`（全球最低）、`asiaMinPrice`、`localMinPrice`、`usMinPrice`、`fen95ReferencePrice`（95分参考）、`otherPlatformMinPrice`（其他平台）、`leakInfos[].leakPrice`（跨区漏出价）。
> 价格单位是「币种最小单位数值」，带小数币种（CNY/USD/EUR…）即分，除 100 得主单位。JPY/KRW 等无小数币种此接口返回值异常，勿用。

> **目录区 vs 价格区**：第 1 步固定用 US 拉目录，第 2 步用你要的 `region/currency/countryCode` 查价 —— 代码里已解耦（`dewu_client.CATALOG_REGION`）。

---

## 文件说明

| 文件 | 作用 |
|---|---|
| `dewu_client.py` | 核心：签名、网关调用、`query_article()` / `query_articles()` |
| `cli.py` | 命令行入口 |
| `api.py` | FastAPI 接口 |
| `.env` | 凭证（不提交）|

## 返回字段（`query_article`）

```jsonc
{
  "articleNumber": "IJ7058",
  "title": "Adidas Adicolor Classics Firebird Track Jacket",
  "globalSpuId": 10005355339,
  "dwSpuId": 5355339,
  "category": "Apparel",
  "region": "CN",
  "country": "CN",
  "currency": "CNY",
  "found": true,
  "sizes": [
    {
      "size": "XS",
      "globalSkuId": 10626581818,
      "globalMinPrice": 525.0,     // 全球最低价（主单位）
      "asiaMinPrice": 525.0,
      "localMinPrice": null,
      "usMinPrice": null,
      "fen95ReferencePrice": null, // 95分参考价
      "otherPlatformMinPrice": null,
      "leakPrice": 550.0,          // 跨区漏出价
      "leakBuyerRegion": "CN"
    }
  ]
}
```

## 已知限制
- 货号必须**能在 US 目录查到**才有结果（如 `206302-2y2` 查不到）。
- `/bidding/bonded/lowest_price`、分销批量查价等接口需额外**权限包**，当前应用报 `无权调用接口`，本项目未用。
- 依赖签名盐 `048a9c…` 与接口路径，得物若改版需同步更新。
