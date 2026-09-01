/**
 * Product about markdown content. Inlined to avoid raw-loader dependency
 * (Turbopack cannot resolve raw-loader for .md imports).
 */
import { APP_VERSION } from "@/version";

export const aboutMarkdown = `# 关于 智海·观澜 ${APP_VERSION}

> **一个面向复杂工作的超级 Agent**

智海·观澜是一套面向企业复杂工作的智能体平台。它通过多智能体协作、长期记忆、沙箱与可扩展 Skills，帮助团队完成研究、分析、内容生成和工作流自动化。

---

## 核心能力

* **Skills 与工具**：通过内置和自定义技能扩展能力。
* **多智能体协作**：将复杂任务分解并交给合适的智能体处理。
* **沙箱与文件系统**：在隔离环境中安全执行代码、处理文件。
* **上下文与长期记忆**：让任务连续、协作更贴合实际需求。

---

## 开源致谢

智海·观澜基于[上游开源框架](https://github.com/bytedance/deer-flow)构建，并遵循其 **MIT License**。

感谢上游开源框架、[LangChain](https://github.com/langchain-ai/langchain)、[LangGraph](https://github.com/langchain-ai/langgraph)、[Next.js](https://nextjs.org/) 及所有开源贡献者。
`;
