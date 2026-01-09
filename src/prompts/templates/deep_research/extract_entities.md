根据以下搜索结果，提取出所有发现的相关实体/选项。请以 JSON 格式返回结果。

## 原始查询

{{ original_query }}

## 搜索结果

{{ search_results }}

## 提取要求

请提取所有发现的实体，包括：

- **name**: 准确名称
- **category**: 分类/类别
- **brief**: 一句话描述
- **source**: 发现来源
- **priority**: 重要程度 (high/medium/low)

## 输出格式

请返回 JSON 格式，包含：
- entities: 发现的实体列表
- summary: 整体发现摘要
- total_found: 发现的实体总数
- categories: 发现的分类列表

