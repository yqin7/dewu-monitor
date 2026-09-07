# 得物价格/销量查询接口文档

服务启动：

```bash
uvicorn api:app --reload --port 8000
```

Swagger: `http://127.0.0.1:8000/docs`

所有响应均为下方真实调用抓取的样例（尺码数组已截断至 2 条便于阅读）。

---

## 接口总览

路由约定：**`/single`** = 单货号（货号走路径参数）｜ **`/multiple`** = 多货号（货号走请求体）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/single/price/{article}` | 单货号 → 每尺码**价格** |
| GET | `/single/sales/{article}` | 单货号 → 每尺码**30天销量** |
| GET | `/single/price-and-sales/{article}` | 单货号 → 每尺码**价格 + 销量** ⭐ |
| POST | `/multiple/price` | 多货号 → 价格 |
| POST | `/multiple/sales` | 多货号 → 销量 |
| POST | `/multiple/price-and-sales` | 多货号 → 价格 + 销量 ⭐ |
| GET | `/health` | 健康检查 |

> 命名约定：URL 路径统一小写 + 连字符（kebab-case），多词字段用复数 `sales`。
> 多货号接口返回的是对应单货号结构的**数组**。

通用参数（`price` / `price-and-sales` 支持；`sales` 为全球口径，无此参数）：

| 参数 | 默认 | 说明 |
|---|---|---|
| `region` | `CN` | 价格地区码 |
| `currency` | `CNY` | 币种 |
| `country_code` | 同 region | 国家码 |

## 1. GET `/health`

```bash
curl http://127.0.0.1:8000/health
```
```json
{"status":"ok"}
```

---

## 2. GET `/single/price/{article}` — 单货号价格

```bash
curl http://127.0.0.1:8000/single/price/IJ7058
curl "http://127.0.0.1:8000/single/price/IJ7058?region=US&currency=USD&country_code=US"
```

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
      "globalMinPrice": 525.0,        // 全球最低价
      "asiaMinPrice": 525.0,          // 亚洲最低价
      "localMinPrice": null,
      "usMinPrice": null,
      "fen95ReferencePrice": null,    // 95分参考价
      "otherPlatformMinPrice": null,  // 其他平台最低价
      "leakPrice": 550.0,             // 跨区漏出价
      "leakBuyerRegion": "CN"
    }
  ]
}
```

---

## 3. GET `/single/sales/{article}` — 单货号销量

销量是**全球口径**，与 region 无关，故无查询参数。

```bash
curl http://127.0.0.1:8000/single/sales/IJ7058
```

```jsonc
{
  "articleNumber": "IJ7058",
  "title": "Adidas Adicolor Classics Firebird Track Jacket",
  "globalSpuId": 10005355339,
  "dwSpuId": 5355339,
  "category": "Apparel",
  "region": "US",
  "found": true,
  "totalSoldNum30": 3475,             // 全尺码 30 天总销量
  "sizes": [
    {
      "size": "XS",
      "globalSkuId": 10626581818,
      "globalSoldNum30": 162,          // 30天全球销量
      "localSoldNum30": 0,             // 30天本地销量
      "globalMonthToMonthRatio": 0.0318,  // 环比 +3.18%
      "localMonthToMonthRatio": 0.0
    },
    {
      "size": "S",
      "globalSkuId": 10626581819,
      "globalSoldNum30": 937,
      "localSoldNum30": 0,
      "globalMonthToMonthRatio": -0.0178,
      "localMonthToMonthRatio": 0.0
    }
  ]
}
```

---

## 4. GET `/single/price-and-sales/{article}` — 单货号价格 + 销量 ⭐

```bash
curl http://127.0.0.1:8000/single/price-and-sales/IJ7058
curl "http://127.0.0.1:8000/single/price-and-sales/IJ7058?region=US&currency=USD"
```

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
  "totalSoldNum30": 3475,
  "sizes": [
    {
      "size": "XS",
      "globalSkuId": 10626581818,
      "globalMinPrice": 525.0,
      "asiaMinPrice": 525.0,
      "localMinPrice": null,
      "usMinPrice": null,
      "fen95ReferencePrice": null,
      "otherPlatformMinPrice": null,
      "leakPrice": 550.0,
      "leakBuyerRegion": "CN",
      "globalSoldNum30": 162,
      "localSoldNum30": 0,
      "globalMonthToMonthRatio": 0.0318,
      "localMonthToMonthRatio": 0.0
    },
    {
      "size": "S",
      "globalSkuId": 10626581819,
      "globalMinPrice": 435.0,
      "asiaMinPrice": 435.0,
      "localMinPrice": null,
      "usMinPrice": null,
      "fen95ReferencePrice": null,
      "otherPlatformMinPrice": null,
      "leakPrice": 435.0,
      "leakBuyerRegion": "CN",
      "globalSoldNum30": 937,
      "localSoldNum30": 0,
      "globalMonthToMonthRatio": -0.0178,
      "localMonthToMonthRatio": 0.0
    }
  ]
}
```

---

## 5. POST `/multiple/price` — 多货号价格

```bash
curl -X POST http://127.0.0.1:8000/multiple/price   -H "Content-Type: application/json"   -d '{"articles":["IJ7058","206302-2Y2"]}'
```

请求体：

```jsonc
{
  "articles": ["IJ7058", "206302-2Y2"],
  "region": "CN",          // 可选
  "currency": "CNY",       // 可选
  "country_code": null     // 可选
}
```

返回是 `/single/price/{article}` 结构的**数组**：

```jsonc
[
  { "articleNumber": "IJ7058",     "found": true, "sizes": [ /* 7 条 */ ] },
  { "articleNumber": "206302-2Y2", "found": true, "sizes": [ /* 8 条 */ ] }
]
```

查不到的货号：

```json
{"articleNumber":"XXXX","found":false,"region":"CN","country":"CN","currency":"CNY","sizes":[]}
```

---

## 6. POST `/multiple/sales` — 多货号销量

请求体只需 `articles`（销量为全球口径）：

```bash
curl -X POST http://127.0.0.1:8000/multiple/sales   -H "Content-Type: application/json"   -d '{"articles":["IJ7058","206302-2Y2"]}'
```

返回是 `/single/sales/{article}` 结构的数组。

---

## 7. POST `/multiple/price-and-sales` — 多货号价格 + 销量 ⭐

```bash
curl -X POST http://127.0.0.1:8000/multiple/price-and-sales   -H "Content-Type: application/json"   -d '{"articles":["IJ7058","206302-2Y2"]}'
```

真实返回（每个货号的 sizes 已截断至 1 条）：

```jsonc
[
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
    "totalSoldNum30": 3475,
    "sizes": [
      {
        "size": "XS",
        "globalSkuId": 10626581818,
        "globalMinPrice": 525.0,
        "asiaMinPrice": 525.0,
        "localMinPrice": null,
        "usMinPrice": null,
        "fen95ReferencePrice": null,
        "otherPlatformMinPrice": null,
        "leakPrice": 550.0,
        "leakBuyerRegion": "CN",
        "globalSoldNum30": 162,
        "localSoldNum30": 0,
        "globalMonthToMonthRatio": 0.0318,
        "localMonthToMonthRatio": 0.0
      }
    ]
  },
  {
    "articleNumber": "206302-2Y2",
    "title": "Crocs Bae Clog EVA Clog 6cm Women's Bone White",
    "globalSpuId": 10005051537,
    "dwSpuId": 5051537,
    "category": "Shoes",
    "region": "CN",
    "country": "CN",
    "currency": "CNY",
    "found": true,
    "totalSoldNum30": 1969,
    "sizes": [
      {
        "size": "33-34",
        "globalSkuId": 10627063227,
        "globalMinPrice": 320.0,
        "asiaMinPrice": 320.0,
        "leakPrice": 335.0,
        "leakBuyerRegion": "CN",
        "globalSoldNum30": 32,
        "localSoldNum30": 0,
        "globalMonthToMonthRatio": -0.0588,
        "localMonthToMonthRatio": 0.0
      }
    ]
  }
]
```

---

## 命令行

```bash
python cli.py IJ7058                    # 仅价格
python cli.py IJ7058 --sales            # 价格 + 销量
python cli.py IJ7058 206302-2Y2         # 多货号
python cli.py IJ7058 --region US --currency USD
python cli.py IJ7058 --json             # JSON 输出
```

`--sales` 输出：

```
IJ7058  Adidas Adicolor Classics Firebird Track Jacket
  globalSpuId=10005355339  类目=Apparel  country=CN  currency=CNY
  30天全球总销量: 3475 件
  尺码      globalSkuId   最低价           漏出价             30天销量     环比
  ----------------------------------------------------------------------
  XS      10626581818   CNY 525.00    CNY 550.00      162       +3.2%
  S       10626581819   CNY 435.00    CNY 435.00      937       -1.8%
  M       10626581820   CNY 405.00    CNY 405.00      703       -0.1%
  L       10626581821   CNY 410.00    CNY 430.00      843       +0.7%
  XL      10626581822   CNY 375.00    CNY 370.00      412       +2.0%
  XXL     10626581823   CNY 375.00    CNY 375.00      397       +4.2%
  XXXL    10626581824   CNY 430.00    CNY 430.00      21        +0.0%
```

---

## Python 直接调用

```python
import dewu_client as dc
dc.load_env()

dc.query_article("IJ7058")                       # 价格
dc.query_article_sales("IJ7058")                 # 销量
dc.query_article_full("IJ7058")                  # 价格+销量
dc.query_articles(["IJ7058", "206302-2Y2"])        # 批量价格
dc.query_articles_sales(["IJ7058", "206302-2Y2"])  # 批量销量
dc.query_articles_full(["IJ7058", "206302-2Y2"])   # 批量价格+销量

# 底层
dc.get_skus_by_article("IJ7058", region="US")    # 货号 -> globalSkuId 列表
dc.batch_price([10626581820], region="CN", currency="CNY")
dc.batch_sales([10626581820])
```

---

## 底层用到的得物开放平台接口

| 官方 apiId | 路径 | 本项目用途 |
|---|---|---|
| 140 | `/intl-commodity/intl/sku/sku-basic-info/by-article-number` | 货号 → globalSpuId + 各尺码 globalSkuId |
| 141 | `/recommend-bid/batchPrice` | 批量查最低价（≤20 个 skuId/次） |
| 159 | `/intl-commodity/intl/sku/sku-basic-info/by-global-sku` | 批量查 30 天销量 |

网关 `https://open.poizon.com`，**无需 access_token**，应用签名即可。

### 三个关键坑（都已在代码中处理）

1. **目录区 vs 价格区**：接口 140 的商品目录只有 **US** 全，CN 区返回空。代码固定用 `CATALOG_REGION="US"` 拉目录，再用你指定的 region 查价（`dewu_client.CATALOG_REGION`）。

2. **统计数据要显式开启**：接口 159 必须传 `statisticsDataQry: {salesEnable: true, minPriceEnable: true}`，否则销量、最低价字段一律返回 `null`。

3. **嵌套对象签名不能排序**：`statisticsDataQry` 是嵌套对象，参与签名时内部 key 必须保持**插入序**（官方 Java SDK 用 Jackson）。排序会导致 `401 签名认证失败`。见 `dewu_client._value_to_string`。

另：接口 140 对货号**区分大小写**（`206302-2y2` 查不到，`206302-2Y2` 可以）。代码已做自动大写重试兜底。

### 单位说明

价格返回的是「币种最小单位数值」，带小数币种（CNY/USD/EUR）即分，代码已 `/100` 转为主单位。
JPY/KRW 等无小数币种此接口返回值异常，勿用。
