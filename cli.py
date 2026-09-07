"""命令行工具：查货号价格。

用法:
    python cli.py IJ7058
    python cli.py IJ7058 206302-001            # 多个货号
    python cli.py IJ7058 --region US --currency USD
    python cli.py IJ7058 --json                # 输出 JSON
"""
from __future__ import annotations

import argparse
import json
import sys

import dewu_client as dc


def _fmt(cur: str, v) -> str:
    return f"{cur} {v:.2f}" if isinstance(v, (int, float)) else "—"


def print_table(res: dict) -> None:
    cur = res.get("currency", "")
    if not res.get("found"):
        print(f"\n[{res['articleNumber']}]  未在 region={res.get('region')} 找到（货号错误或该区未上架）")
        return
    print(f"\n{res['articleNumber']}  {res.get('title')}")
    print(f"  globalSpuId={res.get('globalSpuId')}  类目={res.get('category')}  "
          f"country={res.get('country')}  currency={cur}")
    has_sales = any(s.get("globalSoldNum30") is not None for s in res["sizes"])
    if has_sales:
        print(f"  30天全球总销量: {res.get('totalSoldNum30')} 件")
        print(f"  {'尺码':<8}{'globalSkuId':<14}{'最低价':<14}{'漏出价':<16}{'30天销量':<10}{'环比':<8}")
        print("  " + "-" * 70)
        for s in res["sizes"]:
            leak = _fmt(cur, s.get("leakPrice"))
            ratio = s.get("globalMonthToMonthRatio")
            rr = f"{ratio * 100:+.1f}%" if isinstance(ratio, (int, float)) else "—"
            print(f"  {str(s.get('size')):<8}{s.get('globalSkuId'):<14}"
                  f"{_fmt(cur, s.get('globalMinPrice')):<14}{leak:<16}"
                  f"{str(s.get('globalSoldNum30') if s.get('globalSoldNum30') is not None else '—'):<10}{rr:<8}")
        return
    print(f"  {'尺码':<8}{'globalSkuId':<14}{'最低价':<14}{'亚洲最低':<14}{'漏出价':<16}")
    print("  " + "-" * 62)
    for s in res["sizes"]:
        leak = _fmt(cur, s.get("leakPrice"))
        if s.get("leakBuyerRegion"):
            leak += f"({s['leakBuyerRegion']})"
        print(f"  {str(s.get('size')):<8}{s.get('globalSkuId'):<14}"
              f"{_fmt(cur, s.get('globalMinPrice')):<14}{_fmt(cur, s.get('asiaMinPrice')):<14}{leak:<16}")


def main(argv: list[str]) -> int:
    dc.load_env()
    ap = argparse.ArgumentParser(description="得物海外价格查询")
    ap.add_argument("articles", nargs="+", help="货号，可传多个")
    ap.add_argument("--region", default="CN", help="地区码，默认 CN")
    ap.add_argument("--currency", default="CNY", help="币种，默认 CNY")
    ap.add_argument("--country-code", default=None, help="countryCode，默认同 region")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--sales", action="store_true", help="同时查询 30 天销量")
    args = ap.parse_args(argv[1:])

    if args.sales:
        results = [dc.query_article_full(a.strip(), region=args.region, currency=args.currency,
                                         country_code=args.country_code)
                   for a in args.articles if a.strip()]
    else:
        results = dc.query_articles(args.articles, region=args.region,
                                    currency=args.currency, country_code=args.country_code)
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for res in results:
            print_table(res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
