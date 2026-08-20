# 方法库：社会网络分析（Social Network Analysis, SNA）

**类型**：quantitative（网络结构分析）+ qualitative（情境解释）
**适用**：信息扩散网络、议题共同体、意见领袖识别（社交媒体传播）

## 操作步骤
1. 网络界定：节点（用户/媒体/议题）与关系（转发/引用/共现）的定义
2. 数据获取：社交媒体 API、爬虫（转发链、@提及、标签共现）；媒体互引矩阵
3. 网络构建：邻接矩阵/边表；有向/无向、加权/无权
4. 节点指标：度（degree）、中心性（betweenness/ closeness/ eigenvector）、PageRank
5. 网络指标：密度（density）、平均路径长度、聚类系数、连通分量
6. 社区发现：模块度优化（Louvain）、k-core 分解
7. 扩散分析：传播级联（cascade）、关键扩散路径、时序传播模式
8. 可视化与报告：Gephi/NetDraw 图 + 指标表 + 结构解释

## 注意事项
- 边界问题：网络切分标准需明确（如某话题全部转发链）
- 动态性：快照网络 vs 时序网络（动态 SNA）
- 与内容结合：网络结构分析需结合节点内容（谁在传什么话语）
- 工具：Python（networkx）、Gephi、Pajek；中文平台注意数据合规

## 代表文献
Wasserman & Faust (1994, Social Network Analysis); Borgatti et al. (2018, Analyzing Social Networks)
