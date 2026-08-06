# 方法库：语料库语言学分析（Corpus-based Discourse Analysis）

**类型**：quantitative（语料驱动）+ qualitative（话语解释）
**适用**：大规模媒体文本的系统性语言分析（搭配、词频、话语模式）

## 操作步骤
1. 语料库构建：代表性与平衡性（媒体类型、时段、主题）；规模（一般百万字级）；标注元数据（国家、时间、媒体）
2. 词频分析（frequency）：高频词、关键词（keyword analysis，与参考语料对比，用对数似然比/卡方）
3. 搭配分析（collocation）：目标词的显著搭配词（互信息 MI / T-score / logDice）
4. 索引行分析（concordance）：目标词的上下文语境，人工归类话语模式
5. 语义韵（semantic prosody）：搭配词的情感/评价倾向（积极/消极/中性）
6. 话语模式归纳：将语言证据上升为话语策略（结合批判性话语分析）
7. 报告：统计表 + 典型索引行摘录 + 话语解释

## 注意事项
- 语料可比性：跨国比较需统一采样标准与语料规模
- 词形还原（lemmatization）与分词一致性（中文用 jieba 等）
- 统计显著 ≠ 话语显著：高频词需回到语境解释
- 工具：AntConc、WordSmith、Python（NLTK/spaCy/lingcorpora）；中文语料注意分词质量

## 代表文献
Baker (2006, Using Corpora in Discourse Analysis); 中国语境：媒体语料库话语研究
