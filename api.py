"""得物价格/销量查询 FastAPI 接口。

启动:
    pip install -r requirements.txt
    uvicorn api:app --reload --port 8000

路由约定:
    /single/...    单货号，货号走路径参数
    /multiple/...  多货号，货号走请求体
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

import dewu_client as dc

dc.load_env()
app = FastAPI(title="得物价格/销量查询", version="2.0")

single = APIRouter(prefix="/single", tags=["单货号"])
multiple = APIRouter(prefix="/multiple", tags=["多货号"])


class ArticlesReq(BaseModel):
    articles: List[str] = Field(..., description="货号列表", examples=[["IJ7058", "206302-2Y2"]])
    region: str = "CN"
    currency: str = "CNY"
    country_code: Optional[str] = None


class ArticlesSalesReq(BaseModel):
    """销量为全球口径，与地区无关，故无 region/currency 参数。"""
    articles: List[str] = Field(..., description="货号列表", examples=[["IJ7058", "206302-2Y2"]])


def _guard(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except dc.DewuError as e:
        raise HTTPException(status_code=502, detail=str(e))


# ── 单货号 ────────────────────────────────────────────────────────────────────

@single.get("/price/{article}", summary="单货号 · 每尺码价格")
def single_price(article: str,
                 region: str = Query("CN"),
                 currency: str = Query("CNY"),
                 country_code: Optional[str] = Query(None)):
    return _guard(dc.query_article, article, region=region,
                  currency=currency, country_code=country_code)


@single.get("/sales/{article}", summary="单货号 · 每尺码 30 天销量")
def single_sales(article: str):
    return _guard(dc.query_article_sales, article)


@single.get("/price-and-sales/{article}", summary="单货号 · 每尺码价格 + 销量")
def single_price_and_sales(article: str,
                           region: str = Query("CN"),
                           currency: str = Query("CNY"),
                           country_code: Optional[str] = Query(None)):
    return _guard(dc.query_article_full, article, region=region,
                  currency=currency, country_code=country_code)


# ── 多货号 ────────────────────────────────────────────────────────────────────

@multiple.post("/price", summary="多货号 · 每尺码价格")
def multiple_price(req: ArticlesReq):
    return _guard(dc.query_articles, req.articles, region=req.region,
                  currency=req.currency, country_code=req.country_code)


@multiple.post("/sales", summary="多货号 · 每尺码 30 天销量")
def multiple_sales(req: ArticlesSalesReq):
    return _guard(dc.query_articles_sales, req.articles)


@multiple.post("/price-and-sales", summary="多货号 · 每尺码价格 + 销量")
def multiple_price_and_sales(req: ArticlesReq):
    return _guard(dc.query_articles_full, req.articles, region=req.region,
                  currency=req.currency, country_code=req.country_code)


app.include_router(single)
app.include_router(multiple)


@app.get("/health", tags=["系统"])
def health():
    return {"status": "ok"}
