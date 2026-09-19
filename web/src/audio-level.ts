import type { RefObject } from "react";

export type VoiceVisualState = "idle" | "listening" | "thinking" | "talking";

export type AudioSignal = {
  state: VoiceVisualState;
  read: () => number;
  readInput: () => number;
};

export type AudioSignalRef = RefObject<AudioSignal>;

export function rmsLevel(samples: Float32Array) {
  let sum = 0;
  for (const sample of samples) sum += sample * sample;
  return Math.sqrt(sum / Math.max(1, samples.length));
}

export function amplitude(samples: Float32Array, gain = 5) {
  const rms = rmsLevel(samples);
  return Math.min(1, Math.max(0, rms - 0.006) * gain);
}

export function microphoneMotion(rms: number) {
  return Math.min(1, Math.max(0, rms - 0.004) * 8.5);
}

export function smoothLevel(current: number, target: number, dt: number) {
  const speed = target > current ? 13.2 : 3.12;
  return current + (target - current) * (1 - Math.exp(-speed * dt));
}
