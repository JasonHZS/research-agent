/**
 * LangGraph Generative UI Components
 *
 * 这些组件会被 LangGraph Server 自动打包并提供给 Agent Chat UI。
 * 组件通过 push_ui_message() 从 Python graph 节点触发。
 */
import "./styles.css";

// ============================================================================
// 研究进度组件 - 显示章节研究进度
// ============================================================================

interface Section {
  title: string;
  description: string;
  status: "pending" | "researching" | "completed";
}

interface ResearchProgressProps {
  sections: Section[];
  currentPhase: string;
}

const ResearchProgress = ({ sections, currentPhase }: ResearchProgressProps) => {
  const completed = sections.filter((s) => s.status === "completed").length;
  const total = sections.length;
  const progress = total > 0 ? (completed / total) * 100 : 0;

  return (
    <div className="research-progress">
      <div className="progress-header">
        <span className="phase-badge">{currentPhase}</span>
        <span className="progress-text">
          {completed}/{total} 章节完成
        </span>
      </div>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${progress}%` }} />
      </div>
      <div className="sections-list">
        {sections.map((section, idx) => (
          <div key={idx} className={`section-item status-${section.status}`}>
            <span className="status-icon">
              {section.status === "completed"
                ? "✓"
                : section.status === "researching"
                  ? "⟳"
                  : "○"}
            </span>
            <span className="section-title">{section.title}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

// ============================================================================
// 发现项目卡片 - 显示 discover 阶段发现的实体
// ============================================================================

interface DiscoveredItem {
  name: string;
  category: string;
  brief: string;
  source: string;
  urls: string[];
}

interface DiscoveredItemsProps {
  items: DiscoveredItem[];
  queryType: string;
}

const DiscoveredItems = ({ items, queryType }: DiscoveredItemsProps) => {
  return (
    <div className="discovered-items">
      <div className="items-header">
        <h3>🔍 发现 {items.length} 个相关项目</h3>
        <span className="query-type-badge">{queryType}</span>
      </div>
      <div className="items-grid">
        {items.map((item, idx) => (
          <div key={idx} className="item-card">
            <div className="item-category">{item.category}</div>
            <h4 className="item-name">{item.name}</h4>
            <p className="item-brief">{item.brief}</p>
            {item.urls.length > 0 && (
              <div className="item-links">
                {item.urls.slice(0, 2).map((url, i) => (
                  <a
                    key={i}
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="item-link"
                  >
                    {new URL(url).hostname.replace("www.", "")}
                  </a>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

// ============================================================================
// 来源卡片 - 显示研究引用的来源
// ============================================================================

interface SourceCardProps {
  sources: string[];
  sectionTitle: string;
}

const SourceCard = ({ sources, sectionTitle }: SourceCardProps) => {
  return (
    <div className="source-card">
      <div className="source-header">
        <span className="source-icon">📚</span>
        <span className="source-title">{sectionTitle} - 参考来源</span>
      </div>
      <ul className="source-list">
        {sources.map((source, idx) => (
          <li key={idx} className="source-item">
            {source.startsWith("http") ? (
              <a href={source} target="_blank" rel="noopener noreferrer">
                {source}
              </a>
            ) : (
              source
            )}
          </li>
        ))}
      </ul>
    </div>
  );
};

// ============================================================================
// 澄清问题组件 - 交互式澄清界面
// ============================================================================

import { useStreamContext } from "@langchain/langgraph-sdk/react-ui";

interface ClarifyQuestionProps {
  question: string;
  options?: string[];
}

const ClarifyQuestion = ({ question, options }: ClarifyQuestionProps) => {
  const { submit } = useStreamContext();

  const handleOptionClick = (option: string) => {
    submit({ messages: [{ type: "human", content: option }] });
  };

  return (
    <div className="clarify-question">
      <div className="question-header">
        <span className="question-icon">❓</span>
        <p className="question-text">{question}</p>
      </div>
      {options && options.length > 0 && (
        <div className="question-options">
          {options.map((option, idx) => (
            <button
              key={idx}
              className="option-button"
              onClick={() => handleOptionClick(option)}
            >
              {option}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

// ============================================================================
// 工具调用状态 - 显示正在执行的工具
// ============================================================================

interface ToolCallStatusProps {
  toolName: string;
  args: Record<string, unknown>;
  status: "running" | "completed" | "error";
}

const ToolCallStatus = ({ toolName, args, status }: ToolCallStatusProps) => {
  const statusEmoji = {
    running: "⏳",
    completed: "✅",
    error: "❌",
  };

  return (
    <div className={`tool-call-status status-${status}`}>
      <span className="tool-status-icon">{statusEmoji[status]}</span>
      <span className="tool-name">{toolName}</span>
      {args.query && (
        <span className="tool-query">: {String(args.query).slice(0, 50)}...</span>
      )}
    </div>
  );
};

// ============================================================================
// 导出组件映射
// ============================================================================

export default {
  research_progress: ResearchProgress,
  discovered_items: DiscoveredItems,
  source_card: SourceCard,
  clarify_question: ClarifyQuestion,
  tool_call_status: ToolCallStatus,
};
