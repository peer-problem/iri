import assert from "node:assert/strict";
import { test } from "node:test";
import { parseProvider, providerLabel } from "../src/provider.ts";

test("provider metadata is accepted only from the API contract", () => {
  assert.equal(parseProvider("kanana"), "kanana");
  assert.equal(parseProvider("luna"), "luna");
  assert.equal(parseProvider("unavailable"), "unavailable");
  assert.equal(parseProvider("unknown"), undefined);
  assert.equal(parseProvider(null), undefined);
});

test("the attribution reflects the provider that produced the answer", () => {
  assert.equal(providerLabel("kanana"), "답변 모델: Kanana");
  assert.equal(providerLabel("luna"), "답변 모델: Luna 대체 경로");
  assert.equal(providerLabel(), "답변 모델: 연결 확인 중");
});
