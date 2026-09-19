import assert from "node:assert/strict";
import { test } from "node:test";
import {
  amplitude,
  microphoneMotion,
  rmsLevel,
  smoothLevel,
} from "../src/audio-level.ts";

test("silence stays still and loud signals stay bounded", () => {
  assert.equal(amplitude(new Float32Array(1024)), 0);
  assert.equal(amplitude(new Float32Array(1024).fill(0.003)), 0);
  assert.equal(amplitude(new Float32Array(1024).fill(2)), 1);
  assert.ok(
    amplitude(new Float32Array(1024).fill(0.1)) >
      amplitude(new Float32Array(1024).fill(0.03)),
  );
});

test("the animation envelope attacks quickly and is frame-rate independent", () => {
  assert.ok(smoothLevel(0, 1, 0.1) > 1 - smoothLevel(1, 0, 0.1));
  let at30 = 0;
  let at120 = 0;
  for (let index = 0; index < 30; index++) {
    at30 = smoothLevel(at30, 0.8, 1 / 30);
  }
  for (let index = 0; index < 120; index++) {
    at120 = smoothLevel(at120, 0.8, 1 / 120);
  }
  assert.ok(Math.abs(at30 - at120) < 1e-6);
});

test("the microphone meter keeps the raw level while motion is more sensitive", () => {
  const samples = new Float32Array(1024).fill(0.02);
  assert.ok(Math.abs(rmsLevel(samples) - 0.02) < 1e-6);
  assert.ok(microphoneMotion(rmsLevel(samples)) > amplitude(samples, 7));
  assert.equal(microphoneMotion(0), 0);
  assert.ok(microphoneMotion(0.5) <= 1);
});
