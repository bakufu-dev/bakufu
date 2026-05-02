// API クライアント（fetch ラッパ）
// 詳細設計書 §確定 B に従って実装。直接 fetch() の呼び出しは禁止。
//
// Authorization ヘッダー付与方針（§確定 B 追記）:
//   Gate action POST（approve / reject / cancel）のみ付与。
//   GET リクエストを含む他の全エンドポイントへは送信しない（最小権限原則）。
//   付与が必要な呼び出し元（useGateAction）が headers? 引数で個別指定する。

import type { ApiError } from "./types";

const baseURL = import.meta.env.VITE_API_BASE_URL as string;

const defaultHeaders: Record<string, string> = {
  "Content-Type": "application/json",
  // Authorization はここに含めない。Gate action POST のみ useGateAction で個別付与する
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

/**
 * POST リクエストを送信する。
 *
 * @param path - API パス（baseURL に付加）
 * @param body - リクエストボディ（省略可）
 * @param headers - 追加ヘッダー（省略可）。defaultHeaders とマージして送信する。
 *                  Gate action POST が Authorization を付与するためのフック。
 */
export async function apiPost<T>(
  path: string,
  body?: unknown,
  headers?: Record<string, string>,
): Promise<T> {
  const response = await fetch(`${baseURL}${path}`, {
    method: "POST",
    headers: { ...defaultHeaders, ...headers },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return handleResponse<T>(response);
}
