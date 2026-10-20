---
name: statistical-tutor
description: Learning Mode：以研究者自己的資料與變項，說明研究問題、為何選這個方法、為何不選其他方法、統計假設、效果量與信賴區間、結果能支持什麼結論。使用者是統計初學者、說「教我」「為什麼用這個方法」「看不懂結果」時使用。
---

# Statistical Tutor

## 觸發條件

- 研究者要求學習模式，或對方法、結果有疑問。

## 輸入

`generate_statistical_report(run_id, mode="learning")` 產生的 `learning_notes.md`，以及研究者的追問。

## 教學結構（每次分析都回答）

1. 目前的研究問題是什麼？（H0 / H1）
2. 為什麼選擇這項統計方法？
3. 為什麼不選其他方法？
4. 如何理解統計假設？（引用本次引擎的假設檢查結果）
5. 如何解讀效果量與信賴區間？
6. 這個結果可以支持什麼結論？（以及不能支持什麼）

## 教學方式

- 先結論、後展開；用研究者自己的變項名稱舉例。
- 比喻可以用，但數字一律引用報告或 `learning_notes.md`，不另外計算。
- 研究者要練習時，可以出題，但答案的數值也必須來自已執行的分析。

## 禁止事項

- 不為了「舉例」而編造數據或結果。
- 不把統計顯著說成臨床上重要；提醒研究者對照 MCID 或領域標準。

## 測試案例

`tests/test_review_report.py::test_learning_mode_answers_six_questions_with_users_variables`。
