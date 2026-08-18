# Method 与实验审稿问题说明（中文）

## 一句话故事

LiveSearchVQA 不是“让一个模型出题，再让另一个模型打分”，而是把**提高产率**和**保证有效性**分开：

- Generator 只负责从新鲜证据中提出更可能合格的候选；
- Quality module 是唯一的录取者，只拒绝、不修题；
- 每个发布题目都携带 P0（图像有用）、P1（construction panel 闭卷均失败）和 P2（同一 panel 给证据均成功）的可回放证书；
- Generator 的自检和拒绝记忆可以省钱，但不能替代最终证书。

## 1. Eq 到底是什么

Eq(prediction, gold) 是两阶段的保守判分：

1. **确定性快速判分**
   - 小写化，去标点和英文冠词，合并空格；
   - 归一化后完全相同则正确；
   - 抽取数字 token，数字不同立即判错；
   - 数字相同但表达形式不同，进入第二阶段。
2. **语义二分类**
   - 判分器只看 question、gold、prediction，不看模型身份、检索轨迹或候选所处阶段；
   - 必须保持实体、地点、日期粒度、正负号、金额单位和数量级；
   - 不设置任意数值误差容忍；
   - 缺失/空响应、API 失败或无法判定不能帮助题目通过，重试后仍失败则丢弃候选。

例子：

- “$1.2 billion”与“1.2 billion”：正确；
- “1.2 billion”与“1.2 million”：错误；
- “May 28, 2027”与“28 May 2027”：正确；
- “May 2027”与“May 28, 2027”：错误；
- “12 km”与“12 miles”：错误。

最终 release 应额外保存：归一化后的答案、命中的规则、语义 judge 结果和 judge 版本。这样审稿人能复算每一个 P1/P2 判断。

## 2. Generator 与 panel 是否独立

当前 Generator 与 panel 的一个成员共享 Doubao 模型家族，另外两个 panel 成员来自 Qwen。因此准确表述是：

> 最终认证使用异构的双 provider panel，但不是三个完全独立的模型家族。

这个披露比笼统声称“独立 panel”更可信。论文不把 P1 写成对所有未来模型的数学保证，而写成对 3 模型 × 4 次采样的**经验性、panel-relative certificate**。

## 3. “P1 泛化到 construction panel 之外”是什么意思

P1 在构建时只证明：参与筛选的模型闭卷答不对。所谓“泛化到 panel 之外”是一个额外实验结论：

1. 冻结 construction panel 并生成数据；
2. 选择从未参与出题或认证的 held-out 模型家族；
3. 对 released items 做 closed-book 测试；
4. 报告 **held-out CB leakage**，即 held-out 模型闭卷答对的题目比例。

若 held-out CB leakage 仍低，说明 panel 没有只筛出“专门难倒自己”的题；若很高，说明 P1 对 panel 过拟合。它不是“所有模型永远答不出来”的保证。

## 4. Construction funnel、通过率和成本怎么报告

每次构建应从同一个不可修改的 run manifest 导出：

N_articles → N_generated → N_P0 → N_P1 → N_P2 → 200_released

每一层同时报告：

- 输入数、输出数、条件通过率；
- 按类型统计的拒绝原因；
- API 调用数、tokens、重试数、延迟和 provider 实际计费；
- 每个 released item 的平均调用数和美元成本。

论文附录当前放入的是**模拟表格模板**，不是实测结果。真实实验应比较 logical cascade 与 exhaustive panel，并验证二者的 accepted-set hash 完全一致。

## 5. Typed rejection taxonomy

稳定的顶层类型有七类，底层仍保存原始代码：

- **G**：生成/格式错误；
- **F**：不是新鲜事件事实；
- **V**：图片与事件或问题不匹配、图片不承担指代消歧；
- **E**：证据不是原文片段、答案或数字不在证据中；
- **N**：P1 失败，即存在闭卷答对；
- **S**：P2 失败，即给了 gold evidence 仍有一次答错；
- **D**：重复、类别上限或构成约束。

这样既能回答“为什么被拒绝”，又能把高频错误蒸馏回 Generator constitution；反馈只改变未来候选分布，不改变当前录取标准。

## 6. 五名专家人工质检

五名专家独立审查全部 200 题，每题判断六个维度：

1. gold answer 正确；
2. evidence 足够；
3. image 与 article 是同一事件/实体；
4. image 能解析 question 中省略的视觉指代；
5. 问题确实需要查询当前网页信息；
6. 整体是否可接受。

每个维度至少 3/5 专家同意才算该题通过。正文引用 item-level majority pass，附录报告 1,000 个 item–expert judgment 的正例率、Fleiss’ κ、全票通过率和分歧说明。

论文中的 200/200、97.1%、κ=.84 等目前均以蓝色和“simulated placeholder”标注；只有在匿名 rating matrix 归档后才能改成真实结果。

## 7. 为什么主表不能单独证明 retrieval 是瓶颈

OR − WS 大只说明“agent 自己搜索时没有实现给 gold evidence 时的能力”，但缺口可能发生在：

- **Retrieval miss**：根本没搜到含答案的页面；
- **Distraction**：搜到了正确页面，也搜到冲突/过期页面，最后跟错；
- **Utilization**：正确证据已在检索结果中，但抽取、阅读或综合错误；
- **Other**：工具超时、API 失败或无法分类。

因此需要保存 top-k 结果、打开页面、引用和最终答案。论文只有在真实 trace label 中 retrieval miss 占错误的大多数，并给出 item bootstrap confidence interval 后，才能写“retrieval is the limiting stage”。当前 67.8% 的堆叠图是醒目标注的模拟占位图。

## 8. 六个实验的完整逻辑

| 实验 | 核心问题 | 为什么必须做 | 支持的论文结论 |
|---|---|---|---|
| Exp. 1 Release validity | 能否稳定构造完整 200 题，机器与专家都通过？ | 先证明 benchmark 本身有效 | 数据可信 |
| Exp. 2 Agent diagnosis | CB、WS、OR 和错误轨迹是什么关系？ | 建立 benchmark 测到的科学现象 | 搜索执行产生模型差异；检索是否为主要瓶颈 |
| Exp. 3 Generation ablation | evidence-first、自检、拒绝记忆是否提高各层 yield？ | 严格 verifier 即使配低效 generator 也能凑够 200 题 | Generator 是有作用的方法贡献，而非提示词包装 |
| Exp. 4 Certification ablation | 单 judge/同家族/异构 panel、early stop/exhaustive 有何差别？ | 验证 certificate 的覆盖和早停的严格等价性 | 认证可信且省成本；P1 可测试地迁移到 held-out 模型 |
| Exp. 5 Visual necessity | 移除、遮挡或交换图片会怎样？ | 图文相似不等于图片对回答有因果作用 | 这是 visual search benchmark，不是带装饰图的文本 QA |
| Exp. 6 Efficiency & stability | 调用、成本、人工一致性和跨日期结果是否稳定？ | 单日、昂贵或无法复现的 benchmark 价值有限 | 方法实用、可维护、结论不依赖某一天新闻 |

逻辑顺序是：

> Exp. 1–2 证明“数据有效且现象存在” → Exp. 3–5 证明“现象来自我们声称的机制” → Exp. 6 证明“机制在成本、人工和时间上可用”。

## 提交前必须替换的内容

- 附录 construction funnel、API calls 和 cost；
- 五专家完整 rating matrix 及真实统计；
- 12 个 agent 的主表和 Figure 4；
- 基于真实 retrieval logs 的 Figure 5 和 error decomposition；
- held-out family 的 CB leakage / oracle failure；
- 多日期构建的稳定性和置信区间。
