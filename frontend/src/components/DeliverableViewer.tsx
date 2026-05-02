// DeliverableViewer — LLM 生成 Markdown をサニタイズしてレンダリング
// 詳細設計書 §確定 F: rehype-sanitize + defaultSchema 必須
// XSS 防止: dangerouslySetInnerHTML 禁止

import type React from "react";
import ReactMarkdown from "react-markdown";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";

interface DeliverableViewerProps {
  bodyMarkdown: string;
  /** セクションの見出し（省略可）。aria-labelledby に使用 */
  sectionId?: string;
}

// rehype-sanitize の defaultSchema をそのまま使用（script / iframe / style を除外済み）
const sanitizeSchema = defaultSchema;

export function DeliverableViewer({
  bodyMarkdown,
  sectionId,
}: DeliverableViewerProps): React.ReactElement {
  const contentId = sectionId ?? "deliverable-content";

  return (
    <article
      id={contentId}
      className="prose prose-sm max-w-none p-4 bg-white rounded-md border border-gray-200"
    >
      <ReactMarkdown rehypePlugins={[[rehypeSanitize, sanitizeSchema]]}>
        {bodyMarkdown}
      </ReactMarkdown>
    </article>
  );
}
