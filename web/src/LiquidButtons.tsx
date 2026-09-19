import { Children, useEffect, useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import {
  Frame,
  Glass,
  GlassContainer,
  HStack,
  LiquidCanvas,
  Padding,
  Transform,
  easing,
} from "@liquid-dom/react";

export function LiquidButtons({ children }: { children: ReactNode }) {
  const items = Children.toArray(children);
  const initialCount = useRef(items.length);
  const [fallback, setFallback] = useState(!("gpu" in navigator));
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const [spread, setSpread] = useState(reduced);

  useEffect(() => {
    const timer = window.setTimeout(() => setSpread(true), 450);
    return () => window.clearTimeout(timer);
  }, []);

  const offset = (index: number) =>
    ((initialCount.current - 1) / 2 - index) * 52;

  return (
    <div
      className={`liquid-buttons ${fallback ? "glass-fallback" : ""}`}
      style={{ width: items.length * 52 + 16 }}
      data-glass-engine={fallback ? "css-fallback" : "liquid-dom"}
    >
      {!fallback && (
        <LiquidCanvas
          className="liquid-button-surface"
          canvasStyle={{ width: "100%", height: "100%" }}
          maxDpr={2}
          onError={() => setFallback(true)}
        >
          <Padding insets={12}>
            <GlassContainer
              blur={0}
              spacing={0}
              bezelWidth={2}
              displacementFactor={0}
              reflectionOffset={0}
              tint={{ r: 1, g: 1, b: 1, a: 0.92 }}
              specularStrength={1.2}
              specularWidth={1}
              shadowColor={{ r: 0.23, g: 0.18, b: 0.35, a: 0.18 }}
              shadowBlur={7}
              shadowOffsetY={3}
              shadowSpread={0}
            >
              <HStack spacing={8}>
                {items.map((_, index) => (
                  <Transform
                    key={index}
                    x={spread ? 0 : offset(index)}
                    transition={{ x: easing({ duration: reduced ? 0 : 0.55 }) }}
                  >
                    <Frame width={44} height={44}>
                      <Glass cornerRadius={22} cornerSmoothing={0} />
                    </Frame>
                  </Transform>
                ))}
              </HStack>
            </GlassContainer>
          </Padding>
        </LiquidCanvas>
      )}
      <div className="voice-buttons">
        {items.map((item, index) => (
          <div
            key={index}
            className={`voice-button-slot ${index < initialCount.current ? "voice-button-initial" : "voice-button-added"}`}
            style={{ "--gather-x": `${offset(index)}px` } as CSSProperties}
          >
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}
