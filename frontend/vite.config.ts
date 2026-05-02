import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // ホスト: コンテナ内全インターフェース。ホスト公開は docker-compose ports の
    // "127.0.0.1:5173:5173" バインドで制御する（threat-model.md §docker-compose A3）
    host: "0.0.0.0",
    // Vite 5+ はホスト検証でリクエストを拒否する場合がある。明示的に許可する。
    allowedHosts: ["localhost", "127.0.0.1"],
    // コンテナ外（ブラウザ側）が接続する HMR WebSocket ポートを固定する。
    // コンテナ内ポートと一致させることで HMR 接続を確立できる。
    hmr: {
      clientPort: 5173,
    },
  },
});
