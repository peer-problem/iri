export type Provider = "kanana" | "luna" | "unavailable";

export function parseProvider(value: unknown): Provider | undefined {
  return value === "kanana" || value === "luna" || value === "unavailable"
    ? value
    : undefined;
}

export function providerLabel(provider?: Provider): string {
  if (provider === "kanana") return "답변 모델: Kanana";
  if (provider === "luna") return "답변 모델: Luna 대체 경로";
  if (provider === "unavailable") return "답변 모델: 연결할 수 없음";
  return "";
}
