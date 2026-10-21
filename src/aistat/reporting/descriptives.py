"""Descriptive statistics."""

from __future__ import annotations

from .. import apa
from ..methods import MethodSpec


class DescriptivesReport:
    def headline(self, plan, s) -> str:
        return f"已計算 {len(s['variables'])} 個變項的描述統計（共 {s['n_rows']} 列）"

    def primary_p(self, s) -> float | None:
        return None

    def effect(self, s):
        return None

    def paragraph(self, plan, s, lang) -> str:
        zh = lang == "zh"
        numeric = [v for v in s["variables"] if v["kind"] == "numeric"]
        categorical = [v for v in s["variables"] if v["kind"] == "categorical"]
        parts = [f"資料共 {s['n_rows']} 列；各變項以有效值計算。" if zh
                 else f"The data set has {s['n_rows']} rows; each variable is summarised over its valid values."]
        if numeric:
            head = ("| 變項 | n | 缺失 | M | SD | Mdn | Q1–Q3 | 範圍 |" if zh
                    else "| Variable | n | Missing | M | SD | Mdn | Q1–Q3 | Range |")
            rows = [head, "|---|---|---|---|---|---|---|---|"]
            for v in numeric:
                rows.append(f"| {v['name']} | {v['n']} | {v['missing']} | {apa.num(v['mean'])} | {apa.num(v['sd'])} | "
                            f"{apa.num(v['median'])} | {apa.num(v['q1'])}–{apa.num(v['q3'])} | "
                            f"{apa.num(v['min'])}–{apa.num(v['max'])} |")
            parts.append("\n".join(rows))
        if categorical:
            head = "| 變項 | 類別 | n | % |" if zh else "| Variable | Category | n | % |"
            rows = [head, "|---|---|---|---|"]
            for v in categorical:
                for f in v["frequencies"]:
                    pct = apa.pct(f["proportion"]) if f["proportion"] is not None else "NA"
                    rows.append(f"| {v['name']} | {f['level']} | {f['count']} | {pct} |")
                if v["missing"]:
                    rows.append(f"| {v['name']} | {'缺失' if zh else 'Missing'} | {v['missing']} | — |")
            parts.append("\n".join(rows) + "\n\n" + ("百分比以有效值為分母。" if zh else "Percentages use valid values as the denominator."))
        return "\n\n".join(parts)

    def limitations(self, lang) -> str:
        if lang == "zh":
            return "描述性統計只摘要這份樣本，不進行推論；偏態分布時中位數與四分位距比平均數與標準差更具代表性。"
        return ("Descriptive statistics summarise this sample only and make no inference; for skewed variables the "
                "median and interquartile range are more representative than the mean and SD.")

    def learning(self, plan, results, spec: MethodSpec) -> str:
        s = results["statistics"]
        names = "、".join(f"`{v['name']}`" for v in s["variables"])
        skew = [v for v in s["variables"] if v["kind"] == "numeric" and v["sd"] and v["mean"] is not None
                and abs(v["mean"] - v["median"]) > 0.5 * v["sd"]]
        skew_text = ("、".join(f"`{v['name']}`（M = {apa.num(v['mean'])}, Mdn = {apa.num(v['median'])}）" for v in skew)
                     + " 的平均數與中位數差距大，可能偏態或有極端值，報告時以中位數與四分位距為主。") if skew else \
            "數值變項的平均數與中位數接近，沒有明顯偏態的跡象（仍建議畫直方圖確認）。"
        return f"""# 學習筆記：{spec.name_zh}

## 1. 目前的研究問題是什麼？

{names} 在這份樣本中的分布長什麼樣子？有多少缺失？

## 2. 為什麼選擇描述性統計？

所有研究都需要先描述樣本：論文的「樣本特性」表格、檢查資料是否合理（範圍、缺失、極端值），都來自描述性統計。

## 3. 為什麼不選其他方法？

描述性統計不檢定假設。若要比較組別或檢驗關聯，請在描述之後另外建立 t 檢定、卡方或相關等分析計畫。

## 4. 如何理解統計假設？

描述性統計本身沒有推論假設，但要選對摘要方式：
- scale 變項：平均數（M）與標準差（SD）；偏態時用中位數（Mdn）與四分位距（Q1–Q3）。
- 類別變項：次數與百分比。
{skew_text}

## 5. 如何解讀效果量與信賴區間？

描述性統計沒有效果量；SD 與四分位距描述資料分散程度，SD 越大代表個體差異越大。

## 6. 這個結果可以支持什麼結論？

只能描述「這份樣本」，不能推論到母體；若樣本不是隨機抽樣，代表性也需要討論。
"""
