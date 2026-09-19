export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function request(path: string, init: RequestInit = {}) {
  const response = await fetch(`/api${path}`, {
    ...init,
    credentials: "same-origin",
    signal: init.signal ?? AbortSignal.timeout(100_000),
  });
  if (!response.ok) {
    if (path === "/transcribe" && response.status === 422) {
      throw new ApiError(
        422,
        "목소리가 들리지 않았어요. 마이크 가까이에서 다시 이야기해 주세요.",
      );
    }
    const message =
      response.status === 401
        ? "연결 정보를 확인한 뒤 페이지를 새로고침해 주세요."
        : response.status === 429
          ? "잠시 쉬었다가 다시 시도해 주세요."
          : response.status === 413
            ? "녹음이 너무 길어요. 조금 짧게 이야기해 주세요."
            : "연결이 잠시 원활하지 않아요. 다시 시도해 주세요.";
    throw new ApiError(response.status, message);
  }
  return response;
}

export function jsonRequest(path: string, body: unknown, signal?: AbortSignal) {
  return request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
}
