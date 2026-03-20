# Agent 工具清单

本文档根据当前代码统计：**默认研究 Agent**（`create_research_agent`）与 **Deep Research 图**（`--deep-research`）中显式绑定的工具，并补充 **DeepAgents 框架** 自动注入的工具说明。

统计基准：仓库路径 `src/agent/research_agent.py`、`src/agent/subagents/content_reader_agent.py`、`src/deep_research/utils/tools.py`（2025-03-20 版本）。

---

## 一、默认研究 Agent（CLI / `python -m src.main`）

由 `create_research_agent()` 构建：主 Agent 持有 `main_tools`，并通过 DeepAgents 的 `task` 工具委派子 Agent `content-reader-agent`。

### 1. 主 Agent：`main_tools`（共 **21** 个 LangChain 工具）


| #   | 工具名（LLM 可见）                       | 说明                                  | 实现模块                           |
| --- | --------------------------------- | ----------------------------------- | ------------------------------ |
| 1   | `get_huggingface_papers_tool`     | Hugging Face 论文列表（日/周/月等）           | `src/tools/hf_daily_papers.py` |
| 2   | `get_huggingface_blog_posts_tool` | Hugging Face 博客文章                   | `src/tools/hf_blog.py`         |
| 3   | `get_arxiv_paper_tool`            | 按 ArXiv ID 获取单篇论文信息                 | `src/tools/arxiv_api.py`       |
| 4   | `search_arxiv_papers_tool`        | ArXiv 检索                            | `src/tools/arxiv_api.py`       |
| 5   | `get_zyte_article_list_tool`      | 从博客/资讯站点拉取文章列表（Zyte）                | `src/tools/zyte_reader.py`     |
| 6   | `github_search_tool`              | GitHub 仓库 / Issue / Commit 搜索（无需登录） | `src/tools/github_search.py`   |
| 7   | `tavily_search_tool`              | 通用网页搜索（Tavily）                      | `src/tools/tavily_search.py`   |
| 8   | `list_rss_feeds_tool`             | 列出 OPML 中的 RSS 源                    | `src/tools/rss_feeds.py`       |
| 9   | `fetch_rss_articles_tool`         | 按源抓取 RSS 文章                         | `src/tools/rss_feeds.py`       |
| 10  | `get_feeds_latest_overview_tool`  | 各源最新标题+日期速览                         | `src/tools/rss_feeds.py`       |
| 11  | `get_hn_top_stories`              | HN Top                              | `src/tools/hacker_news.py`     |
| 12  | `get_hn_best_stories`             | HN Best                             | 同上                             |
| 13  | `get_hn_new_stories`              | HN New                              | 同上                             |
| 14  | `get_hn_ask_stories`              | Ask HN                              | 同上                             |
| 15  | `get_hn_show_stories`             | Show HN                             | 同上                             |
| 16  | `get_hn_job_stories`              | HN 招聘帖                              | 同上                             |
| 17  | `get_hn_item`                     | 指定 HN 条目详情                          | 同上                             |
| 18  | `get_hn_comments`                 | HN 评论                               | 同上                             |
| 19  | `get_hn_user`                     | HN 用户资料                             | 同上                             |
| 20  | `get_hn_max_item_id`              | 当前最大 item ID                        | 同上                             |
| 21  | `get_hn_updates`                  | 最近变更条目/用户                           | 同上                             |


### 2. 子 Agent：`content-reader-agent`（共 **2** 个工具，阅读器二选一）


| 工具名                                                 | 说明                                                                                          | 实现模块                                                    |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| `get_jina_reader_tool` **或** `get_zyte_reader_tool` | 网页正文转 Markdown；由环境变量 `CONTENT_READER_TYPE` 决定（`jina` / `zyte`，默认见 `src/config/settings.py`） | `src/tools/jina_reader.py` / `src/tools/zyte_reader.py` |
| `github_readme_tool`                                | 读取 GitHub 仓库 README                                                                         | `src/tools/github_search.py`                            |


**运行时**：子 Agent 始终暴露 **2** 个工具名，其中阅读类工具在任一时刻只有 **1** 个生效（Jina 或 Zyte）。

### 3. DeepAgents 框架附加（主 Agent，非 `main_tools` 手写注册）

`create_deep_agent` 通过中间件还会提供（名称以库实现为准，常见包括）：

- `write_todos`：任务列表规划（`TodoListMiddleware`）
- `ls`、`read_file`、`write_file`、`edit_file`、`glob`、`grep`、`execute`：虚拟文件系统与可选执行（`FilesystemMiddleware`；`execute` 依赖后端是否支持沙箱）
- `task`：调用子 Agent（`SubAgentMiddleware`；本项目注册子 Agent `content-reader-agent`）

详见依赖包 `deepagents` 中 `create_deep_agent` 的文档字符串（`graph.py`）。

---

## 二、Deep Research 模式（`--deep-research`）

图构建见 `src/deep_research/graph.py`，研究员工具来自 `get_all_research_tools()`。

### 1. `get_all_research_tools()`（共 **20** 个工具）

与主 Agent 的差异简述：

- **包含**：ArXiv（2）、HF 论文/博客（2）、`get_zyte_article_list_tool`、`github_search_tool`、`github_readme_tool`、`tavily_search_tool`、HN 全套（11）、以及 **Jina 或 Zyte 阅读器（1）**。
- **不包含**：RSS 三件套（`list_rss_feeds_tool`、`fetch_rss_articles_tool`、`get_feeds_latest_overview_tool`）。

实现：`src/deep_research/utils/tools.py`。

### 2. Researcher / Discover 子图额外工具

`get_researcher_tools(all_research_tools)` 在 above 列表基础上再增加 **2** 个：


| 工具名                 | 说明         |
| ------------------- | ---------- |
| `research_complete` | 标记当前章节研究完成 |
| `think`             | 记录规划性思考    |


实现：`src/deep_research/structured_outputs.py`。

因此 **Researcher 绑定工具总数 = 20 + 2 = 22**。

### 3. 澄清节点（Clarify）

`_get_clarify_tools()` 仅绑定：

- `tavily_search_tool`

实现：`src/deep_research/nodes/clarify.py`。

---

## 三、仓库中已有但未接入上述 Agent 的工具

以下在 `src/tools/` 中存在，但 **未** 出现在 `create_research_agent` 的 `main_tools` 或 `get_all_research_tools()` 中：

- `bocha_web_search_tool` — `src/tools/bocha_search.py`（博查搜索）

若将来接入，需改 `research_agent.py` 或 `deep_research/utils/tools.py` 并更新本文档。

---

## 四、数量汇总


| 范围                             | 数量            | 说明                                 |
| ------------------------------ | ------------- | ---------------------------------- |
| 主 Agent 业务工具 `main_tools`      | **21**        | 不含框架 `write_todos` / 文件系统 / `task` |
| 子 Agent 业务工具                   | **2**（阅读 1 选） | Jina 与 Zyte 阅读器不会同时出现              |
| Deep Research 研究员工具集           | **20**        | `get_all_research_tools()`         |
| Deep Research Researcher + 完成类 | **22**        | + `research_complete`、`think`      |
| Deep Research 澄清阶段             | **1**         | `tavily_search_tool`               |


**说明**：Hacker News 使用 **Firebase JSON API**（`src/tools/hacker_news.py`），不经过 MCP。

---

## 五、维护

新增或删除工具时，请同步修改：

- `src/agent/research_agent.py`（默认主 Agent）
- `src/agent/subagents/content_reader_agent.py`（内容子 Agent）
- `src/deep_research/utils/tools.py`（Deep Research）
- 本文档 `docs/agent_tools.md`

