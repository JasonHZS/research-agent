分析以下用户查询，识别查询类型和期望输出格式。

## 用户查询

{{ query }}

## 判断标准

### 查询类型 (query_type)

**重要：只选择一个最主要的查询类型**，即使查询涉及多个方面。优先级从高到低：

1. **list**: 询问"有哪些"、"哪些选项"、"什么工具/模型/框架"等，需要枚举多个实体（如果查询核心是"列举/发现"，即使后续有对比需求，也选 list）
2. **comparison**: 询问"A和B的区别"、"对比分析"、"优缺点比较"（仅当比较对象已明确给出时）
3. **deep_dive**: 针对单一主题深入研究，如"X的原理"、"如何实现Y"
4. **general**: 其他类型的查询

### 输出格式 (output_format)

- **table**: 用户明确要求表格，或列表型查询适合表格展示
- **list**: 用户要求清单式输出
- **prose**: 适合文章/报告形式

### 是否需要前置探索 (needs_discovery)

- list 类型查询通常需要先发现所有选项，再逐个深入研究
- 如果用户问"有哪些X"，且X是需要枚举的实体类型，则设为 true

## 输出要求

请返回以下格式的 JSON（注意：每个字段只能填一个值，不是数组）：

```json
{
  "query_type": "<list、comparison、deep_dive和general中的其中一个>",
  "output_format": "<table、list和prose中的其中一个>",
  "needs_discovery": true,
  "discovery_target": "<要发现的目标类型（可选）>",
  "reasoning": "<分析理由>"
}
```

- `query_type`: 只填 "list"、"comparison"、"deep_dive" 或 "general" 其中之一（字符串，不是数组）
- `output_format`: 只填 "table"、"list" 或 "prose" 其中之一
