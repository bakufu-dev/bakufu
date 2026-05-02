// Layout — 全ページを包む共通レイアウト
// NavBar: bakufu ロゴ（/へのリンク）+ Directive 投入リンク + ConnectionIndicator
// 基本設計: §コンポーネント設計 Layout

import type React from "react";
import { Link, Outlet } from "react-router";
import { useWebSocketState } from "../hooks/useWebSocketBus";
import { ConnectionIndicator } from "./ConnectionIndicator";

export function Layout(): React.ReactElement {
  const wsState = useWebSocketState();

  return (
    <div className="min-h-screen bg-gray-50">
      {/* NavBar */}
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200 shadow-sm">
        <nav
          className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between gap-4"
          aria-label="メインナビゲーション"
        >
          {/* ロゴ / ホームリンク */}
          <Link
            to="/"
            className="text-lg font-bold text-gray-900 hover:text-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 rounded"
          >
            bakufu
          </Link>

          {/* 右側: Directive 投入 + 接続状態 */}
          <div className="flex items-center gap-4">
            <Link
              to="/directives/new"
              className="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              + Directive 投入
            </Link>
            <ConnectionIndicator state={wsState} />
          </div>
        </nav>
      </header>

      {/* ページコンテンツ */}
      <main className="max-w-5xl mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
