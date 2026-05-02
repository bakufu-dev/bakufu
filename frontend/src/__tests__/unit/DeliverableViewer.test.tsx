// TC-UT-CD-007: Markdown → HTML 変換
// TC-UT-CD-008: XSS — <script> タグが sanitize される（T1 / §確定 F）
// TC-UT-CD-009: <REDACTED:...> がそのまま文字列表示される（R1-4）
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DeliverableViewer } from "../../components/DeliverableViewer";

describe("TC-UT-CD-007: DeliverableViewer — Markdown → HTML 変換", () => {
  it("# Title と段落が HTML タグに変換される", async () => {
    const { container } = render(<DeliverableViewer bodyMarkdown={"# Title\n\nParagraph text"} />);

    // h1 タグが存在する
    const h1 = container.querySelector("h1");
    expect(h1).not.toBeNull();
    expect(h1?.textContent).toBe("Title");

    // p タグが存在する
    const p = container.querySelector("p");
    expect(p).not.toBeNull();
    expect(p?.textContent).toBe("Paragraph text");
  });

  it("article 要素にレンダリングされる", () => {
    const { container } = render(<DeliverableViewer bodyMarkdown="content" />);
    expect(container.querySelector("article")).not.toBeNull();
  });
});

describe("TC-UT-CD-008: DeliverableViewer — XSS 防止（T1 / §確定 F）", () => {
  it("<script> タグが sanitize されて article DOM に存在しない", () => {
    // 良性テキストを先に置いて別ブロックとして独立させる
    const { container } = render(
      <DeliverableViewer bodyMarkdown={"Benign content\n\n<script>alert('xss')</script>"} />,
    );

    // <script> タグが article 内に存在しない（rehype-sanitize の defaultSchema が除去）
    const article = container.querySelector("article");
    expect(article).not.toBeNull();
    const scriptInArticle = article?.querySelector("script");
    expect(scriptInArticle).toBeNull();

    // 良性コンテンツは表示される
    expect(article?.textContent).toContain("Benign content");
  });

  it("onmouseover 等のイベントハンドラ属性が除去される", () => {
    const { container } = render(
      // p タグを含む markdown — rehype-sanitize で onmouseover が除去される
      <DeliverableViewer
        bodyMarkdown={'Safe paragraph\n\n<p onmouseover="alert(1)">safe text</p>'}
      />,
    );
    const article = container.querySelector("article");
    expect(article).not.toBeNull();
    // sanitize 後、onmouseover 属性が除去されている
    const pWithHandler = article?.querySelector("[onmouseover]");
    expect(pWithHandler).toBeNull();
  });
});

describe("TC-UT-CD-009: DeliverableViewer — <REDACTED:...> 文字列そのまま表示（R1-4）", () => {
  it("token: <REDACTED:DISCORD_WEBHOOK> が文字列として表示される", () => {
    render(<DeliverableViewer bodyMarkdown={"token: <REDACTED:DISCORD_WEBHOOK>"} />);
    expect(screen.getByText(/REDACTED:DISCORD_WEBHOOK/)).toBeInTheDocument();
  });
});
