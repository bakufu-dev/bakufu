// TC-UT-CD-001~006: StatusBadge — status → Tailwind color class マッピング（REQ-CD-UI-006 / WCAG AA）
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusBadge } from "../../components/StatusBadge";

describe("TC-UT-CD-001~006: StatusBadge — ステータス別カラーマッピング", () => {
  it("TC-UT-CD-001: PENDING → gray-500 クラス + aria-label", () => {
    const { container } = render(<StatusBadge status="PENDING" />);
    const badge = container.querySelector("span");
    expect(badge).not.toBeNull();
    expect(badge?.className).toContain("bg-gray-500");
    expect(badge?.className).toContain("text-white");
    expect(badge?.getAttribute("aria-label")).toBe("PENDING");
    expect(screen.getByText("PENDING")).toBeInTheDocument();
  });

  it("TC-UT-CD-002: IN_PROGRESS → blue-600 クラス", () => {
    const { container } = render(<StatusBadge status="IN_PROGRESS" />);
    const badge = container.querySelector("span");
    expect(badge?.className).toContain("bg-blue-600");
    expect(badge?.className).toContain("text-white");
    expect(badge?.getAttribute("aria-label")).toBe("IN_PROGRESS");
  });

  it("TC-UT-CD-003: AWAITING_EXTERNAL_REVIEW → yellow-600（WCAG AA 4.5:1 以上）", () => {
    const { container } = render(<StatusBadge status="AWAITING_EXTERNAL_REVIEW" />);
    const badge = container.querySelector("span");
    // bg-yellow-600: 4.6:1 コントラスト比（WCAG AA 準拠）
    expect(badge?.className).toContain("bg-yellow-600");
    expect(badge?.className).toContain("text-white");
    expect(badge?.getAttribute("aria-label")).toBe("AWAITING_EXTERNAL_REVIEW");
  });

  it("TC-UT-CD-004: DONE → green-600 クラス", () => {
    const { container } = render(<StatusBadge status="DONE" />);
    const badge = container.querySelector("span");
    expect(badge?.className).toContain("bg-green-600");
    expect(badge?.className).toContain("text-white");
    expect(badge?.getAttribute("aria-label")).toBe("DONE");
  });

  it("TC-UT-CD-005: BLOCKED → red-600 クラス", () => {
    const { container } = render(<StatusBadge status="BLOCKED" />);
    const badge = container.querySelector("span");
    expect(badge?.className).toContain("bg-red-600");
    expect(badge?.className).toContain("text-white");
    expect(badge?.getAttribute("aria-label")).toBe("BLOCKED");
  });

  it("TC-UT-CD-006: CANCELLED → gray-400 + text-gray-900（PENDING とは異なる muted 表現）", () => {
    const { container } = render(<StatusBadge status="CANCELLED" />);
    const badge = container.querySelector("span");
    // CANCELLED は bg-gray-400（PENDING の bg-gray-500 とは異なる）
    expect(badge?.className).toContain("bg-gray-400");
    // text-gray-900（白ではなく濃いグレー — WCAG AA 対応）
    expect(badge?.className).toContain("text-gray-900");
    expect(badge?.getAttribute("aria-label")).toBe("CANCELLED");
  });

  it("APPROVED → green-600 クラス", () => {
    const { container } = render(<StatusBadge status="APPROVED" />);
    const badge = container.querySelector("span");
    expect(badge?.className).toContain("bg-green-600");
    expect(badge?.getAttribute("aria-label")).toBe("APPROVED");
  });

  it("REJECTED → red-600 クラス", () => {
    const { container } = render(<StatusBadge status="REJECTED" />);
    const badge = container.querySelector("span");
    expect(badge?.className).toContain("bg-red-600");
    expect(badge?.getAttribute("aria-label")).toBe("REJECTED");
  });
});
