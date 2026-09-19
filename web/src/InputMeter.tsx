import { useEffect, useState } from "react";
import type { AudioSignalRef } from "./audio-level";

export function InputMeter({ signal }: { signal: AudioSignalRef }) {
  const [reading, setReading] = useState({ db: -Infinity, active: false });

  useEffect(() => {
    const update = () => {
      const active = signal.current.state === "listening";
      const rms = active ? signal.current.readInput() : 0;
      setReading({ active, db: rms > 0 ? 20 * Math.log10(rms) : -Infinity });
    };
    update();
    const timer = window.setInterval(update, 80);
    return () => window.clearInterval(timer);
  }, [signal]);

  const level = Math.min(1, Math.max(0, (reading.db + 60) / 60));
  const label = !reading.active
    ? "마이크 꺼짐"
    : Number.isFinite(reading.db)
      ? `${Math.round(reading.db)} dBFS`
      : "−∞ dBFS";

  return (
    <div className="input-meter">
      <span className="sr-only">입력 레벨 {label}</span>
      <div
        className="input-meter-bars"
        role="meter"
        aria-label="마이크 입력 레벨"
        aria-valuemin={-60}
        aria-valuemax={0}
        aria-valuenow={Math.min(
          0,
          Math.max(-60, Number.isFinite(reading.db) ? reading.db : -60),
        )}
        aria-valuetext={label}
      >
        {Array.from({ length: 28 }, (_, index) => (
          <i
            key={index}
            data-lit={reading.active && (index + 1) / 28 <= level}
          />
        ))}
      </div>
    </div>
  );
}
