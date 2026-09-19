const MAX_AUDIO_BYTES = 20 * 1024 * 1024;

type SpeechMetadata = {
  requestId: string;
  bytes: number;
  segments: number;
  sha256: string;
};

type ParsedEvent = {
  name: string;
  data: unknown;
};

export class SpeechStreamError extends Error {
  readonly code: string;

  constructor(code: string, message = "Invalid speech stream") {
    super(message);
    this.name = "SpeechStreamError";
    this.code = code;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function integer(value: unknown): value is number {
  return Number.isSafeInteger(value) && Number(value) >= 0;
}

function parseBlock(block: string): ParsedEvent {
  let name: string | undefined;
  let data: string | undefined;
  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith("event: ") && name === undefined) {
      name = line.slice(7);
    } else if (line.startsWith("data: ") && data === undefined) {
      data = line.slice(6);
    } else {
      throw new SpeechStreamError("malformed_event");
    }
  }
  if (!name || data === undefined) {
    throw new SpeechStreamError("malformed_event");
  }
  try {
    return { name, data: JSON.parse(data) };
  } catch {
    throw new SpeechStreamError("invalid_json");
  }
}

class EventParser {
  private readonly decoder = new TextDecoder("utf-8", { fatal: true });
  private buffer = "";

  push(chunk: Uint8Array): ParsedEvent[] {
    try {
      this.buffer += this.decoder.decode(chunk, { stream: true });
    } catch {
      throw new SpeechStreamError("invalid_utf8");
    }
    return this.drain();
  }

  finish(): ParsedEvent[] {
    try {
      this.buffer += this.decoder.decode();
    } catch {
      throw new SpeechStreamError("invalid_utf8");
    }
    const events = this.drain();
    if (this.buffer.trim()) throw new SpeechStreamError("truncated_event");
    this.buffer = "";
    return events;
  }

  private drain(): ParsedEvent[] {
    const events: ParsedEvent[] = [];
    while (true) {
      const separator = this.buffer.match(/\r?\n\r?\n/);
      if (!separator?.index && separator?.index !== 0) break;
      const block = this.buffer.slice(0, separator.index);
      this.buffer = this.buffer.slice(separator.index + separator[0].length);
      if (!block) throw new SpeechStreamError("malformed_event");
      events.push(parseBlock(block));
    }
    return events;
  }
}

function decodeAudio(value: unknown): Uint8Array {
  if (typeof value !== "string" || !value) {
    throw new SpeechStreamError("invalid_audio");
  }
  try {
    const binary = atob(value);
    if (!binary.length || binary.length % 2) {
      throw new SpeechStreamError("invalid_audio");
    }
    return Uint8Array.from(binary, (character) => character.charCodeAt(0));
  } catch (error) {
    if (error instanceof SpeechStreamError) throw error;
    throw new SpeechStreamError("invalid_audio");
  }
}

export async function sha256Hex(bytes: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}

export async function consumeVerifiedSpeech(
  response: Response,
  onAudio: (audio: Uint8Array) => void,
): Promise<SpeechMetadata> {
  if (!response.headers.get("content-type")?.startsWith("text/event-stream")) {
    throw new SpeechStreamError("invalid_content_type");
  }
  if (!response.body) throw new SpeechStreamError("missing_body");

  const expectedRequestId = response.headers.get("x-request-id");
  const parser = new EventParser();
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let requestId: string | undefined;
  let totalBytes = 0;
  let segmentBytes = 0;
  let segmentCount = 0;
  let started = false;
  let done: SpeechMetadata | undefined;
  let failed = true;

  const checkRequest = (payload: Record<string, unknown>) => {
    if (typeof payload.requestId !== "string" || !payload.requestId) {
      throw new SpeechStreamError("invalid_request_id");
    }
    requestId ??= payload.requestId;
    if (
      payload.requestId !== requestId ||
      (expectedRequestId !== null && payload.requestId !== expectedRequestId)
    ) {
      throw new SpeechStreamError("request_id_mismatch");
    }
  };

  const handle = (event: ParsedEvent) => {
    if (done) throw new SpeechStreamError("event_after_done");
    if (!isRecord(event.data)) throw new SpeechStreamError("invalid_payload");
    checkRequest(event.data);

    if (event.name === "audio.started") {
      if (
        started ||
        event.data.encoding !== "pcm_s16le" ||
        event.data.sampleRate !== 24_000 ||
        event.data.channels !== 1
      ) {
        throw new SpeechStreamError("invalid_start");
      }
      started = true;
      return;
    }

    if (!started) throw new SpeechStreamError("missing_start");
    if (event.name === "audio.delta") {
      if (event.data.segment !== segmentCount) {
        throw new SpeechStreamError("segment_mismatch");
      }
      const audio = decodeAudio(event.data.audio);
      totalBytes += audio.byteLength;
      segmentBytes += audio.byteLength;
      if (totalBytes > MAX_AUDIO_BYTES) {
        throw new SpeechStreamError("audio_too_long");
      }
      chunks.push(audio);
      onAudio(audio);
      return;
    }

    if (event.name === "audio.segment_done") {
      if (
        event.data.segment !== segmentCount ||
        event.data.segmentBytes !== segmentBytes ||
        event.data.totalBytes !== totalBytes ||
        !integer(event.data.attempts) ||
        event.data.attempts < 1
      ) {
        throw new SpeechStreamError("segment_mismatch");
      }
      segmentCount += 1;
      segmentBytes = 0;
      return;
    }

    if (event.name === "audio.error") {
      const code =
        typeof event.data.code === "string" && event.data.code
          ? event.data.code
          : "upstream_error";
      throw new SpeechStreamError(`server_${code}`, "Speech stream failed");
    }

    if (event.name === "audio.done") {
      if (
        !totalBytes ||
        segmentBytes !== 0 ||
        event.data.bytes !== totalBytes ||
        event.data.segments !== segmentCount ||
        typeof event.data.sha256 !== "string" ||
        !/^[0-9a-f]{64}$/.test(event.data.sha256)
      ) {
        throw new SpeechStreamError("invalid_completion");
      }
      done = {
        requestId: requestId!,
        bytes: totalBytes,
        segments: segmentCount,
        sha256: event.data.sha256,
      };
      return;
    }

    throw new SpeechStreamError("unknown_event");
  };

  try {
    while (true) {
      const { done: ended, value } = await reader.read();
      if (ended) break;
      for (const event of parser.push(value)) handle(event);
    }
    for (const event of parser.finish()) handle(event);
    if (!done) throw new SpeechStreamError("missing_completion");

    const audio = new Uint8Array(totalBytes);
    let offset = 0;
    for (const chunk of chunks) {
      audio.set(chunk, offset);
      offset += chunk.byteLength;
    }
    if ((await sha256Hex(audio.buffer)) !== done.sha256) {
      throw new SpeechStreamError("checksum_mismatch");
    }
    failed = false;
    return done;
  } finally {
    if (failed) await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
