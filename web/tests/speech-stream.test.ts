import assert from "node:assert/strict";
import { test } from "node:test";
import {
  consumeVerifiedSpeech,
  sha256Hex,
  SpeechStreamError,
} from "../src/speech-stream.ts";

function event(name: string, data: Record<string, unknown>) {
  return new TextEncoder().encode(
    `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`,
  );
}

function response(parts: Uint8Array[], requestId = "request-1") {
  return new Response(
    new ReadableStream({
      start(controller) {
        for (const part of parts) controller.enqueue(part);
        controller.close();
      },
    }),
    {
      headers: {
        "Content-Type": "text/event-stream; charset=utf-8",
        "X-Request-Id": requestId,
      },
    },
  );
}

async function validEvents(audio: Uint8Array, requestId = "request-1") {
  const sha256 = await sha256Hex(audio.buffer);
  return [
    event("audio.started", {
      requestId,
      encoding: "pcm_s16le",
      sampleRate: 24_000,
      channels: 1,
    }),
    event("audio.delta", {
      requestId,
      segment: 0,
      audio: Buffer.from(audio).toString("base64"),
    }),
    event("audio.segment_done", {
      requestId,
      segment: 0,
      segmentBytes: audio.byteLength,
      totalBytes: audio.byteLength,
      attempts: 1,
    }),
    event("audio.done", {
      requestId,
      bytes: audio.byteLength,
      segments: 1,
      sha256,
    }),
  ];
}

function splitEveryByte(parts: Uint8Array[]) {
  return parts.flatMap((part) =>
    Array.from(part, (byte) => Uint8Array.of(byte)),
  );
}

test("accepts a complete verified stream across arbitrary chunk boundaries", async () => {
  const audio = Uint8Array.of(1, 0, 2, 0, 3, 0, 4, 0);
  const received: number[] = [];
  const result = await consumeVerifiedSpeech(
    response(splitEveryByte(await validEvents(audio))),
    (chunk) => received.push(...chunk),
  );

  assert.deepEqual(received, [...audio]);
  assert.equal(result.requestId, "request-1");
  assert.equal(result.bytes, audio.byteLength);
  assert.equal(result.segments, 1);
  assert.equal(result.sha256, await sha256Hex(audio.buffer));
});

test("rejects EOF without audio.done", async () => {
  const parts = await validEvents(Uint8Array.of(1, 0));
  await assert.rejects(
    consumeVerifiedSpeech(response(parts.slice(0, -1)), () => {}),
    (error) =>
      error instanceof SpeechStreamError && error.code === "missing_completion",
  );
});

test("rejects an explicit server error", async () => {
  const requestId = "request-1";
  const parts = [
    event("audio.started", {
      requestId,
      encoding: "pcm_s16le",
      sampleRate: 24_000,
      channels: 1,
    }),
    event("audio.error", { requestId, code: "incomplete" }),
  ];
  await assert.rejects(
    consumeVerifiedSpeech(response(parts), () => {}),
    (error) =>
      error instanceof SpeechStreamError && error.code === "server_incomplete",
  );
});

test("rejects completion metadata with a byte mismatch", async () => {
  const parts = await validEvents(Uint8Array.of(1, 0));
  const wrongDone = event("audio.done", {
    requestId: "request-1",
    bytes: 4,
    segments: 1,
    sha256: "0".repeat(64),
  });
  await assert.rejects(
    consumeVerifiedSpeech(response([...parts.slice(0, -1), wrongDone]), () => {}),
    (error) =>
      error instanceof SpeechStreamError && error.code === "invalid_completion",
  );
});

test("rejects a request ID mismatch", async () => {
  await assert.rejects(
    consumeVerifiedSpeech(
      response(await validEvents(Uint8Array.of(1, 0), "request-2")),
      () => {},
    ),
    (error) =>
      error instanceof SpeechStreamError && error.code === "request_id_mismatch",
  );
});

test("rejects unknown and malformed events", async () => {
  const started = event("audio.started", {
    requestId: "request-1",
    encoding: "pcm_s16le",
    sampleRate: 24_000,
    channels: 1,
  });
  await assert.rejects(
    consumeVerifiedSpeech(
      response([started, event("audio.surprise", { requestId: "request-1" })]),
      () => {},
    ),
    (error) =>
      error instanceof SpeechStreamError && error.code === "unknown_event",
  );
  await assert.rejects(
    consumeVerifiedSpeech(
      response([new TextEncoder().encode("event: audio.started\n\n")]),
      () => {},
    ),
    (error) =>
      error instanceof SpeechStreamError && error.code === "malformed_event",
  );
});
