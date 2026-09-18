const SAMPLE_RATE = 24_000;
const MAX_AUDIO_BYTES = 20 * 1024 * 1024;

/** Plays OpenAI's headerless mono PCM while the response is still arriving. */
export class PcmStreamPlayer {
  private sources = new Set<AudioBufferSourceNode>();
  private chunks: Uint8Array[] = [];
  private byteCount = 0;
  private lastByte: number | null = null;
  private nextStart = 0;
  private finished = false;
  private stopped = false;
  hasStarted = false;

  constructor(
    private context: AudioContext,
    private onEnded: () => void,
  ) {}

  push(chunk: Uint8Array) {
    if (this.stopped || this.finished) return;
    this.byteCount += chunk.byteLength;
    if (this.byteCount > MAX_AUDIO_BYTES) throw new Error("Audio is too long");
    this.chunks.push(chunk);

    let bytes = chunk;
    if (this.lastByte !== null) {
      bytes = new Uint8Array(chunk.byteLength + 1);
      bytes[0] = this.lastByte;
      bytes.set(chunk, 1);
    }
    const sampleCount = Math.floor(bytes.byteLength / 2);
    this.lastByte = bytes.byteLength % 2 ? bytes[bytes.byteLength - 1] : null;
    if (!sampleCount) return;

    const buffer = this.context.createBuffer(1, sampleCount, SAMPLE_RATE);
    const samples = buffer.getChannelData(0);
    for (let i = 0; i < sampleCount; i++) {
      const signed = ((bytes[i * 2] | (bytes[i * 2 + 1] << 8)) << 16) >> 16;
      samples[i] = signed / 32768;
    }
    const source = this.context.createBufferSource();
    source.buffer = buffer;
    source.connect(this.context.destination);
    source.onended = () => {
      source.disconnect();
      this.sources.delete(source);
      if (this.finished && !this.sources.size && !this.stopped) this.onEnded();
    };
    this.sources.add(source);
    this.nextStart = Math.max(this.nextStart, this.context.currentTime + 0.06);
    source.start(this.nextStart);
    this.nextStart += buffer.duration;
    this.hasStarted = true;
  }

  finish(): ArrayBuffer {
    if (this.stopped || !this.byteCount || this.lastByte !== null) {
      throw new Error("Incomplete audio");
    }
    this.finished = true;
    const merged = new Uint8Array(this.byteCount);
    let offset = 0;
    for (const chunk of this.chunks) {
      merged.set(chunk, offset);
      offset += chunk.byteLength;
    }
    this.chunks = [];
    if (!this.sources.size) this.onEnded();
    return merged.buffer;
  }

  stop() {
    this.stopped = true;
    this.chunks = [];
    for (const source of this.sources) {
      source.onended = null;
      try { source.stop(); } catch { /* Already ended. */ }
      source.disconnect();
    }
    this.sources.clear();
  }
}
