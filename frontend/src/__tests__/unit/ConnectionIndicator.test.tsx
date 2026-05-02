// TC-UT-CD-016: state=disconnected → 赤 dot + 切断テキスト
// TC-UT-CD-017: state=reconnecting → 黄 dot + MSG-CD-UI-005 ariaLabel
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConnectionIndicator } from "../../components/ConnectionIndicator";

describe("TC-UT-CD-016: ConnectionIndicator — state=disconnected", () => {
  it("赤系 dot クラス（bg-red-500）と ariaLabel が表示される", () => {
    const { container } = render(<ConnectionIndicator state="disconnected" />);

    // 赤 dot 要素
    const dot = container.querySelector(".bg-red-500");
    expect(dot).not.toBeNull();

    // output 要素の aria-label
    const output = container.querySelector("output");
    expect(output).not.toBeNull();
    expect(output?.getAttribute("aria-label")).toBe("サーバーとの接続が切断されました");

    // 切断中テキスト
    expect(screen.getByText("切断中")).toBeInTheDocument();

    // aria-live="polite"
    expect(output?.getAttribute("aria-live")).toBe("polite");
  });
});

describe("TC-UT-CD-017: ConnectionIndicator — state=reconnecting（MSG-CD-UI-005）", () => {
  it("黄 dot（bg-yellow-500）と MSG-CD-UI-005 の ariaLabel が設定される", () => {
    const { container } = render(<ConnectionIndicator state="reconnecting" />);

    // 黄 dot 要素
    const dot = container.querySelector(".bg-yellow-500");
    expect(dot).not.toBeNull();

    // MSG-CD-UI-005: ariaLabel
    const output = container.querySelector("output");
    expect(output?.getAttribute("aria-label")).toBe(
      "サーバーとの接続が切断されました。再接続中...",
    );

    // 再接続中テキスト
    expect(screen.getByText("再接続中...")).toBeInTheDocument();
  });
});

describe("ConnectionIndicator — state=connected", () => {
  it("緑 dot（bg-green-500）と 接続済み ariaLabel", () => {
    const { container } = render(<ConnectionIndicator state="connected" />);

    const dot = container.querySelector(".bg-green-500");
    expect(dot).not.toBeNull();

    const output = container.querySelector("output");
    expect(output?.getAttribute("aria-label")).toBe("サーバーと接続済み");
    expect(screen.getByText("接続済み")).toBeInTheDocument();
  });
});
