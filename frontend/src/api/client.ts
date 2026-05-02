// API クライアント（fetch ラッパ）
// 詳細設計書 §確定 B に従って実装。直接 fetch() の呼び出しは禁止。

import type { ApiError } from "./types";

const baseURL = import.meta.env.VITE_API_BASE_URL as string;

const defaultHeaders: Record<string, string> = {
  "Content-Type": "application/json",
};

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let code = "UNKNOWN_ERROR";
    let message = response.statusText;
    try {
      const body = (await response.json()) as {
        error?: { code?: string; message?: string };
      };
      if (body.error) {
        code = body.error.code ?? code;
        message = body.error.message ?? message;
      }
    } catch {
      // JSON パース失敗時はデフォルト値を使用
    }
    const apiError: ApiError = {
      code,
      message,
      status: response.status,
    };
    throw apiError;
  }
  return response.json() as Promise<T>;
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${baseURL}${path}`, {
    method: "GET",
    headers: defaultHeaders,
  });
  return handleResponse<T>(response);
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${baseURL}${path}`, {
    method: "POST",
    headers: defaultHeaders,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return handleResponse<T>(response);
}
