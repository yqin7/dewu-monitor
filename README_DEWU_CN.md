# 得物国内开放平台 (open.dewu.com) 调用备忘（备用）

> 本项目主用**海外** POIZON（见 `README.md`，无需 token）。
> 这份是**国内** dop 开放平台的备用文档，走 **OAuth 授权码模式**，需要 code 换 token。
>
> ⚠️ 重要结论：**国内开放平台是商家侧，没有"平台实时最低价/行情价"接口。**
> 全量 273 个接口里价格字段只有三类：你自己的出价、官方售价(`auth_price`/MSRP)、订单结算金额。
> 要行情价请用海外 POIZON 的 `recommend-bid`。国内这套只适合：货号→spu_id/sku_id/尺码/官方价 的商品档案。

---

## 1. 环境与网关

| 用途 | 地址 |
|---|---|
| API 生产网关 | `https://openapi.dewu.com` |
| API 沙箱网关 | `https://openapi-sandbox.dewu.com`（固定假数据，仅验证管道）|
| 授权页 | `https://open.dewu.com/#/authorize` |
| 换 token | `https://open.dewu.com/api/v1/h5/passport/v1/oauth2/token` |
| 刷新 token | `https://open.dewu.com/api/v1/h5/passport/v1/oauth2/refresh_token` |

**凭证**（应用详情页获取）：`app_key` / `app_secret`。放 `.env`：
```
DEWU_APP_KEY=生产AppKey
DEWU_APP_SECRET=生产AppSecret
```

**两道必过的闸**：
1. **IP 白名单** —— 调用 IP 必须加入 应用详情 → IP白名单（点保存，即时生效，无需审核）。
   否则报 `5025 当前IP不在应用白名单里面`。家宽 IP 会变，换网络要重加。
2. **授权 token** —— ISV/第三方应用调业务接口必须带 `access_token`（自研商家用 app_key 即可，免授权）。

---

## 2. OAuth 授权码流程（code → token → refresh）

### 2.1 第一步：获取授权码 code

浏览器打开授权页（`redirect_uri` 必须与应用配置的回调地址一致，且 **encodeURIComponent 编码**）：

```
https://open.dewu.com/#/authorize?response_type=code&client_id=<APP_KEY>&scope=all&redirect_uri=<ENCODED_REDIRECT_URI>
```

| 参数 | 必填 | 值 |
|---|---|---|
| `response_type` | 是 | 固定 `code` |
| `client_id` | 是 | 应用 AppKey |
| `redirect_uri` | 是 | 与应用回调地址一致（encodeURIComponent 编码）|
| `scope` | 是 | 固定 `all` |
| `state` | 否 | 透传，原样返回 |

登录授权后，浏览器跳到 `redirect_uri?code=xxxx&state=...`。
> 回调地址就算是无法打开的假域名（如 `https://gougoutou/...`）也没关系 —— **直接从地址栏抄 `?code=` 后面那串**即可。
> **code 是一次性的，有效期仅几分钟，过期或用过即失效**（报 `无效的authorization_code`）。

### 2.2 第二步：code 换 access_token

`POST https://open.dewu.com/api/v1/h5/passport/v1/oauth2/token`，`Content-Type: application/json`：

```json
{
  "client_id": "<APP_KEY>",
  "client_secret": "<APP_SECRET>",
  "authorization_code": "<上一步的 code>"
}
```

返回：
```json
{
  "code": 200,
  "data": {
    "access_token": "xxxx",
    "access_token_expires_in": 86400,      // 秒。实测 ≈24h（文档写 31536000 不可信，以返回值为准）
    "refresh_token": "yyyy",
    "refresh_token_expires_in": 86400,
    "open_id": "该应用下同一用户恒定",
    "scope": ["all"]
  }
}
```
> 注意 token 请求**不需要 sign**，只用 client_id + client_secret + code。

### 2.3 第三步：刷新 token（过期前续期）

`POST https://open.dewu.com/api/v1/h5/passport/v1/oauth2/refresh_token`：

```json
{
  "client_id": "<APP_KEY>",
  "client_secret": "<APP_SECRET>",
  "refresh_token": "<refresh_token>"
}
```
返回同 2.2 结构，拿到新的 `access_token`。**access_token 有效期只有约 24h，建议起个定时任务用 refresh_token 续期**，否则每天都要重走一次授权页。

---

## 3. 业务接口签名（sign）

每个业务接口（非 token 接口）都要 `sign`。算法与海外一致（见 `dewu_client.create_sign`）：

1. 参数里移除 `sign`/`secret`、移除所有 null 值（空字符串 `""` 保留）；
2. 加入 `app_key`、`timestamp`（毫秒）、`access_token`（ISV 必填）；
3. 按 key 字典序排序；
4. key、value 各自 **Java 风格 URLEncode**（空格→`+`，`*` 不编码，`~`→`%7E`；数组元素用逗号拼接、对象转紧凑 JSON）；
5. 拼成 `k1=v1&k2=v2...`，末尾**直接追加 `app_secret`**；
6. MD5 → **转大写**。

公共请求参数：

| 参数 | 必填 | 说明 |
|---|---|---|
| `app_key` | 是 | 商家标识 |
| `sign` | 是 | 上面算出的签名 |
| `access_token` | ISV 必填 | 授权令牌 |
| `timestamp` | 是 | 当前毫秒时间戳 |

公共响应：`{ "code": 200, "msg": "...", "data": {...} }`，`code=200` 为成功。

---

## 4. 常用接口：根据货号查商品

**[apiId=156] `POST /dop/api/v1/spu/batch_article_number`**（一次最多 5 个货号，建议 1-3 个）

请求业务参数：
```json
{ "article_numbers": ["IJ7058"] }
```
返回（`data` 为数组）关键字段：

| 字段 | 说明 |
|---|---|
| `spu_id` | 商品 SPU id |
| `title` | 商品名 |
| `article_number` / `other_numbers` | 货号 / 辅助货号 |
| `auth_price` | **官方售价（单位：分）** —— 注意是 MSRP，不是行情价 |
| `status` | 上下架（1 上架 / 0 下架）|
| `has_auth` | 该应用对此商品是否有供应链资质 |
| `skus[]` | `sku_id` + `properties`（如 `{"尺码":"40"}`）+ `barcode` |

其它可用商品接口：按品牌/类目拉 SPU、按 spuId/skuId 查等（`商品服务` 分组）。
出价、库存、订单等接口需对应**权限包**，未申请会报 `无权调用接口`。

---

## 5. 最小调用示例（Python）

```python
import hashlib, json, time, requests

APP_KEY = "..."; APP_SECRET = "..."
GATEWAY = "https://openapi.dewu.com"

_SAFE = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.*")
def jenc(s):
    o=[]
    for b in str(s).encode("utf-8"):
        c=chr(b); o.append(c if c in _SAFE else "+" if c==" " else f"%{b:02X}")
    return "".join(o)
def to_str(v):
    if v is None: return ""
    if isinstance(v,bool): return "true" if v else "false"
    if isinstance(v,list): return ",".join(json.dumps(x,ensure_ascii=False,separators=(",",":")) if isinstance(x,(dict,list)) else to_str(x) for x in v)
    if isinstance(v,dict): return json.dumps({k:x for k,x in v.items() if x is not None},ensure_ascii=False,separators=(",",":"),sort_keys=True)
    return str(v)
def sign(p):
    c={k:v for k,v in p.items() if k not in("sign","secret") and v is not None}
    raw="&".join(f"{jenc(k)}={jenc(to_str(c[k]))}" for k in sorted(c))+APP_SECRET
    return hashlib.md5(raw.encode()).hexdigest().upper()

# 1) code 换 token（首次；之后用 refresh_token 续）
def get_token(code):
    r=requests.post("https://open.dewu.com/api/v1/h5/passport/v1/oauth2/token",
        json={"client_id":APP_KEY,"client_secret":APP_SECRET,"authorization_code":code},
        headers={"Content-Type":"application/json"}, timeout=20).json()
    assert r.get("code")==200, r
    return r["data"]["access_token"]

# 2) 带 token + sign 调业务接口
def call(path, biz, token):
    p=dict(biz); p["app_key"]=APP_KEY; p["timestamp"]=int(time.time()*1000)
    p["access_token"]=token; p["sign"]=sign(p)
    return requests.post(GATEWAY+path, json=p,
        headers={"Content-Type":"application/json"}, timeout=25).json()

token = get_token("粘贴新的code")
print(call("/dop/api/v1/spu/batch_article_number", {"article_numbers":["IJ7058"]}, token))
```

---

## 6. 常见报错

| code / msg | 含义 | 处理 |
|---|---|---|
| `5025 当前IP不在应用白名单` | IP 没加白 | 应用详情→IP白名单→加当前出口IP→保存 |
| `401 签名认证失败` | sign 错 | 检查 URLEncode/排序/大写/app_secret 拼接 |
| `无效的authorization_code` | code 过期或已用 | 重新走授权页拿新 code |
| `无权调用接口` | 缺权限包 | 到控制台申请对应权限包 |
| token `access_token_expires_in≈86400` | 约 24h 过期 | 用 refresh_token 定时续期 |

---

## 附：应用信息填写位置

以下值从开放平台控制台「应用详情」获取，**不要写进仓库**，放 `.env`（已 gitignore）：

```
DEWU_APP_KEY=<生产 AppKey>
DEWU_APP_SECRET=<生产 App Secret>
```

- 应用类型：网站应用（ISV），需走 OAuth 授权码模式
- 回调地址：在控制台「回调配置」里填，需与授权链接的 `redirect_uri` 完全一致
- 沙箱环境有独立的 AppKey/Secret，仅返回固定假数据，用于验证签名与调用链路
