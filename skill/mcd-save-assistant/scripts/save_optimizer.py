#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麦门营养管家 - 省钱 + 健康双目标组合推荐算法（离线计算引擎）
================================================
输入麦当劳 MCP query-meals / query-store-coupons / calculate-price / list-nutrition-foods 的真实返回，
在预算约束 + 营养约束（热量上限 / 蛋白下限）下输出 3 类推荐方案：最便宜 / 最划算 / 最丰盛。

用法（作为 MCP 返回数据的后处理引擎）：
    python save_optimizer.py --meals meals.json --coupons coupons.json --budget 40 --max-kcal 900 --min-protein 25

meals.json 结构（对齐 query-meals 返回的 data.meals 字典，营养字段来自 list-nutrition-foods）：
    { "code": {"name": "...", "currentPrice": "55.5", "originalPrice": "65.5", "discountType": null,
               "kcal": 480, "protein": 26.5} }
    kcal/protein 为可选项：来自 list-nutrition-foods，按餐品 code 匹配后并入；缺失时该餐品不参与营养约束判定。
coupons.json 结构（对齐 query-store-coupons 返回数组）：
    [ {"title": "...", "couponId": "...", "couponCode": "...", "products": [{"productCode": "...", "productName": "..."}]} ]
    可选字段：{"price": "9.9"} 表示该券可把商品以固定价购买（券价）

输出：JSON，含 feasible_count / nutrition_filtered / nutrition_constraint / traps（凑单陷阱提示）/
cheapest / best_value / richest 三个方案，
每个方案含 items、原价合计、优惠、应付、总热量(kcal)、总蛋白(g)、蛋白性价比(g/元)。
"""
import argparse
import json
import sys
from itertools import combinations


# 主食判定：名称含以下关键词视为能"吃饱"的主食单品
MAIN_KEYWORDS = ("堡", "套餐", "鸡", "鱼", "牛", "派", "麦满分", "巨无霸", "卷", "饭", "翅", "桶")


def is_main_item(name):
    return any(kw in name for kw in MAIN_KEYWORDS)


def parse_price(v):
    """价格字符串转分（整数），避免浮点误差。"""
    try:
        return int(round(float(v) * 100))
    except (TypeError, ValueError):
        return 0


def build_effective_prices(meals, coupons):
    """
    计算每个餐品的有效单价（分）与可用券。
    规则：
    - currentPrice < originalPrice 时按 currentPrice（促销价）。
    - 若某券明确给出固定券价 price，则适用商品用券后按券价计。
    - 返回 {code: {"name", "unit_price_cents", "orig_price_cents", "discount_type",
                   "coupon": {couponId, couponCode, title} | None}}
    """
    result = {}
    for code, m in meals.items():
        unit = parse_price(m.get("currentPrice"))
        orig = parse_price(m.get("originalPrice"))
        if orig > unit:
            orig = unit  # 促销价视为原价（展示层再体现省额）
        entry = {
            "code": code,
            "name": m.get("name", code),
            "unit_price_cents": unit,
            "orig_price_cents": orig,
            "discount_type": m.get("discountType"),
            "kcal": m.get("kcal"),
            "protein": m.get("protein"),
            "coupon": None,
        }
        # 券匹配：优先固定券价，其次按适用商品匹配（此处仅标记，算价交给 calculate-price）
        for c in coupons:
            products = c.get("products") or []
            if any(p.get("productCode") == code for p in products):
                entry["coupon"] = {
                    "couponId": c.get("couponId"),
                    "couponCode": c.get("couponCode"),
                    "title": c.get("title"),
                    "fixed_price_cents": parse_price(c.get("price")) if c.get("price") else None,
                }
                break
        result[code] = entry
    return result


def combo_cost(combo, effective):
    """计算一个组合（餐品code->数量）的总价（分）、原价合计、优惠额、总热量、总蛋白。"""
    total_cents = 0
    orig_cents = 0
    kcal_total = 0.0
    protein_total = 0.0
    has_nutrition = False
    items = []
    for code, qty in combo.items():
        e = effective[code]
        if e["coupon"] and e["coupon"].get("fixed_price_cents"):
            unit = e["coupon"]["fixed_price_cents"]
        else:
            unit = e["unit_price_cents"]
        total_cents += unit * qty
        orig_cents += e["orig_price_cents"] * qty
        if e.get("kcal") is not None:
            kcal_total += e["kcal"] * qty
            has_nutrition = True
        if e.get("protein") is not None:
            protein_total += e["protein"] * qty
        items.append({
            "code": e["code"],
            "name": e["name"],
            "quantity": qty,
            "unit_price_yuan": unit / 100,
            "discount_type": e["discount_type"],
            "coupon_title": (e["coupon"] or {}).get("title"),
        })
    return {"items": items, "orig_cents": orig_cents, "pay_cents": total_cents,
            "save_cents": orig_cents - total_cents,
            "kcal_total": round(kcal_total, 1) if has_nutrition else None,
            "protein_total": round(protein_total, 1) if has_nutrition else None}


def detect_traps(effective, plans, budget_cents):
    """
    凑单陷阱检测（对齐头部竞品卖点，用官方数据做升级版）：
    1. 券价陷阱：某券固定券价 > 该单品现价（用券反而更贵）
    2. 凑单小食：推荐方案里含无优惠的非主食小食（为凑单多买）
    3. 预算剩余：最便宜方案远低于预算（提示可升级/加购）
    """
    traps = []

    # 1. 券价陷阱
    seen_coupon = set()
    for e in effective.values():
        coupon = e.get("coupon")
        fp = coupon.get("fixed_price_cents") if coupon else None
        if fp is None or e["unit_price_cents"] <= 0:
            continue
        if fp > e["unit_price_cents"]:
            key = coupon.get("couponId") or coupon.get("title")
            if key and key not in seen_coupon:
                seen_coupon.add(key)
                traps.append({
                    "type": "coupon_overpriced",
                    "severity": "high",
                    "title": "用券反而更贵：券「%s」固定价 %.1f 元 > 单品现价 %.1f 元" % (
                        coupon.get("title", "?"), fp / 100, e["unit_price_cents"] / 100),
                    "detail": "%s 现价 %.1f 元，该券却按 %.1f 元结算——别为凑单硬用这张券。" % (
                        e["name"], e["unit_price_cents"] / 100, fp / 100),
                })

    # 2. 凑单小食（对三个推荐方案中每一项判断，按单品去重）
    seen_side = set()
    plan_labels = {"cheapest": "最便宜", "best_value": "最划算", "richest": "最丰盛"}
    for plan_key, plan in plans.items():
        if not plan:
            continue
        for it in plan["items"]:
            if is_main_item(it["name"]) or it["name"] in seen_side:
                continue
            no_discount = not it.get("coupon_title") and it.get("discount_type") in (None, "")
            if no_discount:
                seen_side.add(it["name"])
                save = it["unit_price_yuan"] * it["quantity"]
                traps.append({
                    "type": "side_item",
                    "severity": "medium",
                    "title": "凑单小食：「%s」无任何优惠" % it["name"],
                    "detail": "在「%s」方案中，%s×%d 是无券无促销的凑单项；不需要的话可删掉省 %.1f 元。" % (
                        plan_labels.get(plan_key, plan_key), it["name"], it["quantity"], save),
                })

    # 3. 预算剩余提示
    cheapest = plans.get("cheapest")
    if cheapest and budget_cents > 0:
        pay_cents = round(cheapest["pay_total_yuan"] * 100)
        remain = budget_cents - pay_cents
        if remain > 0 and remain >= budget_cents * 0.3:
            traps.append({
                "type": "budget_left",
                "severity": "low",
                "title": "预算没花满：最便宜方案只花 %.1f 元，还剩 %.1f 元" % (
                    cheapest["pay_total_yuan"], remain / 100),
                "detail": "可在预算内加购饮料/小食提升体验，或直接选用「最划算 / 最丰盛」方案。" ,
            })
    return traps


def recommend(meals, coupons, budget_yuan, people=1, top_n=3, max_kcal=None, min_protein=None):
    """
    生成三类推荐方案。
    budget_yuan: 总预算（元）。max_kcal: 总热量上限（千卡，None=不限制）。
    min_protein: 总蛋白下限（克，None=不限制）。营养字段缺失的组合自动满足营养约束（不影响过滤）。
    """
    effective = build_effective_prices(meals, coupons)
    codes = list(effective.keys())
    budget_cents = int(round(budget_yuan * 100))
    if budget_cents <= 0:
        budget_cents = 99999900  # 未给预算时不做硬约束

    def nutrition_ok(cost):
        """营养约束判定：只对营养字段完整的组合生效。"""
        if max_kcal is not None and cost.get("kcal_total") is not None and cost["kcal_total"] > max_kcal:
            return False
        if min_protein is not None and cost.get("protein_total") is not None and cost["protein_total"] < min_protein:
            return False
        return True

    # 枚举所有可行组合（单品1-3份、至多3个不同单品），受预算约束
    feasible = []
    # 单品重复份数枚举
    for code in codes:
        e = effective[code]
        unit = e["coupon"]["fixed_price_cents"] if e["coupon"] and e["coupon"].get("fixed_price_cents") else e["unit_price_cents"]
        if unit <= 0:
            continue
        for qty in range(1, 4):
            if unit * qty <= budget_cents:
                feasible.append({code: qty})

    # 多品组合（2-3 个不同单品，各1份起）
    for r in (2, 3):
        for combo in combinations(codes, r):
            combo_dict = {}
            ok = True
            for code in combo:
                e = effective[code]
                unit = e["coupon"]["fixed_price_cents"] if e["coupon"] and e["coupon"].get("fixed_price_cents") else e["unit_price_cents"]
                if unit <= 0:
                    ok = False
                    break
                combo_dict[code] = 1
            if not ok:
                continue
            total_cents = 0
            for code, qty in combo_dict.items():
                e = effective[code]
                unit = e["coupon"]["fixed_price_cents"] if e["coupon"] and e["coupon"].get("fixed_price_cents") else e["unit_price_cents"]
                total_cents += unit * qty
            if total_cents <= budget_cents and combo_dict not in feasible:
                feasible.append(combo_dict)

    if not feasible:
        return {"error": "预算过低或菜单为空，无法组合出可行方案", "feasible_count": 0}

    scored = []
    for combo in feasible:
        c = combo_cost(combo, effective)
        # 性价比：每分钱买到的原价价值
        value_ratio = c["orig_cents"] / c["pay_cents"] if c["pay_cents"] > 0 else 0
        scored.append({"combo": combo, "cost": c, "ratio": value_ratio})

    # 去重（相同成本与商品集合）
    seen = set()
    unique = []
    for s in scored:
        key = (tuple(sorted(s["combo"].items())), s["cost"]["pay_cents"])
        if key not in seen:
            seen.add(key)
            unique.append(s)

    # 营养约束过滤：优先在满足热量/蛋白约束的组合中选择；无任何满足时回退全部
    nutrition_pool = [s for s in unique if nutrition_ok(s["cost"])]
    pool_base = nutrition_pool if nutrition_pool else unique

    # 主食判定：名称含关键词视为能"吃饱"的主食单品（见模块级 MAIN_KEYWORDS）

    def has_main(combo):
        for code in combo:
            if is_main_item(effective[code]["name"]):
                return True
        return False

    def fmt(plan):
        protein_per_yuan = None
        if plan["cost"].get("protein_total") is not None and plan["cost"]["pay_cents"] > 0:
            protein_per_yuan = round(plan["cost"]["protein_total"] / (plan["cost"]["pay_cents"] / 100), 2)
        return {
            "items": plan["cost"]["items"],
            "orig_total_yuan": plan["cost"]["orig_cents"] / 100,
            "pay_total_yuan": plan["cost"]["pay_cents"] / 100,
            "save_yuan": plan["cost"]["save_cents"] / 100,
            "item_count": sum(plan["combo"].values()),
            "kcal_total": plan["cost"].get("kcal_total"),
            "protein_total": plan["cost"].get("protein_total"),
            "protein_per_yuan": protein_per_yuan,
        }

    with_main = [s for s in pool_base if has_main(s["combo"])]
    pool = with_main if with_main else pool_base  # 无主食组合时回退全部

    if not pool:
        return {"error": "预算/营养约束过严，无法组合出可行方案", "feasible_count": 0}

    cheapest = min(pool, key=lambda s: s["cost"]["pay_cents"])
    best_value = max(pool, key=lambda s: s["ratio"])
    richest = max(pool, key=lambda s: s["cost"]["orig_cents"])

    plans = {
        "cheapest": fmt(cheapest),
        "best_value": fmt(best_value),
        "richest": fmt(richest),
    }

    return {
        "feasible_count": len(unique),
        "nutrition_filtered": len(nutrition_pool),
        "nutrition_constraint": {
            "max_kcal": max_kcal,
            "min_protein": min_protein,
            "relaxed": bool(nutrition_pool) is False and (max_kcal is not None or min_protein is not None),
        },
        "traps": detect_traps(effective, plans, budget_cents),
        "cheapest": plans["cheapest"],
        "best_value": plans["best_value"],
        "richest": plans["richest"],
    }


def main():
    parser = argparse.ArgumentParser(description="麦门营养管家 - 省钱+健康组合推荐引擎")
    parser.add_argument("--meals", required=True, help="query-meals 返回的 data.meals JSON 文件")
    parser.add_argument("--coupons", required=True, help="query-store-coupons 返回的券数组 JSON 文件")
    parser.add_argument("--budget", type=float, default=0, help="总预算（元），0 表示不限制")
    parser.add_argument("--people", type=int, default=1, help="用餐人数（默认1）")
    parser.add_argument("--max-kcal", type=float, default=None, help="总热量上限（千卡），不填不限制")
    parser.add_argument("--min-protein", type=float, default=None, help="总蛋白下限（克），不填不限制")
    args = parser.parse_args()

    with open(args.meals, "r", encoding="utf-8") as f:
        meals = json.load(f)
    with open(args.coupons, "r", encoding="utf-8") as f:
        coupons = json.load(f)

    result = recommend(meals, coupons, args.budget, args.people,
                       max_kcal=args.max_kcal, min_protein=args.min_protein)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
