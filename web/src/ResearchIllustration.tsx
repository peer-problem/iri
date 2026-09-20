import { useEffect, useRef, useState } from "react";
import { DiagramSelect } from "./DiagramSelect";
import { diagramContent } from "./diagram-content";
import type { IllustrationKind } from "./diagram-content";

export function ResearchIllustration({ kind, caption, paused = false }: { kind: IllustrationKind; caption: string; paused?: boolean }) {
  const content = diagramContent[kind];
  const host = useRef<HTMLDivElement>(null);
  const pausedRef = useRef(paused), modeRef = useRef(0);
  const resumeRef = useRef<(() => void) | null>(null);
  const sceneRef = useRef<ReturnType<typeof import("./research-scene").createResearchScene> | null>(null);
  const [ready, setReady] = useState(false), [mode, setMode] = useState(0), [zoomed, setZoomed] = useState(false);
  useEffect(() => { pausedRef.current = paused; resumeRef.current?.(); }, [paused]);
  useEffect(() => { modeRef.current = mode; sceneRef.current?.setMode(mode); }, [mode]);
  useEffect(() => {
    const container = host.current;
    if (!container) return;
    let disposed = false, visible = false, loading = false, lost = false;
    let frame = 0, previous = 0, elapsed = 0;
    const reduced = matchMedia("(prefers-reduced-motion: reduce)");
    setReady(false);
    const draw = (now: number) => {
      frame = 0;
      if (!sceneRef.current || disposed || lost) return;
      if (previous) elapsed += Math.min((now - previous) / 1000, .06);
      previous = now; sceneRef.current.render(elapsed);
      if (visible && !document.hidden && !reduced.matches && !pausedRef.current) frame = requestAnimationFrame(draw);
    };
    const resume = () => {
      cancelAnimationFrame(frame); previous = 0;
      if (sceneRef.current && visible && !document.hidden && !lost) {
        if (reduced.matches || pausedRef.current) sceneRef.current.render(elapsed);
        else frame = requestAnimationFrame(draw);
      }
    };
    const contextLost = (event: Event) => { event.preventDefault(); lost = true; cancelAnimationFrame(frame); setReady(false); };
    const start = async () => {
      if (loading || sceneRef.current || disposed) return;
      loading = true;
      try {
        const { createResearchScene } = await import("./research-scene");
        if (disposed) return;
        const scene = createResearchScene(container, kind);
        sceneRef.current = scene; scene.setMode(modeRef.current);
        scene.canvas.addEventListener("webglcontextlost", contextLost);
        scene.render(0); setReady(true); resume();
      } catch { if (!disposed) setReady(false); }
    };
    const visibility = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; if (visible) void start(); resume(); }, { rootMargin: "80px" });
    visibility.observe(container);
    const resize = new ResizeObserver(() => sceneRef.current?.resize()); resize.observe(container);
    document.addEventListener("visibilitychange", resume); reduced.addEventListener("change", resume); resumeRef.current = resume;
    return () => {
      disposed = true; cancelAnimationFrame(frame); visibility.disconnect(); resize.disconnect();
      document.removeEventListener("visibilitychange", resume); reduced.removeEventListener("change", resume); resumeRef.current = null;
      sceneRef.current?.canvas.removeEventListener("webglcontextlost", contextLost);
      sceneRef.current?.dispose(); sceneRef.current = null;
    };
  }, [kind]);
  return <figure className={`paper-figure illustration-${kind}`}>
    <div className="diagram-controls"><DiagramSelect label={`${content.title} 보기 선택`} options={content.modes} value={mode} onChange={setMode} /><button className="diagram-zoom" aria-pressed={zoomed} onClick={() => setZoomed(!zoomed)}>{zoomed ? "전체 그림 보기" : "그림 확대"}</button></div>
    <div className="diagram-viewport" data-zoomed={zoomed} tabIndex={zoomed ? 0 : undefined} aria-label={zoomed ? "확대한 그림. 좌우로 스크롤할 수 있습니다." : undefined}>
    <div className={`research-illustration ${ready ? "is-rendered" : ""}`} aria-label={content.title} role="img">
      <div className="diagram-fallback" aria-hidden="true"><span>{content.title}</span><p>{content.notes[mode]}</p></div>
      <div className="illustration-canvas" ref={host} aria-hidden="true" />
      <div className="diagram-labels" aria-hidden="true">{content.labels.map(label => <div className={`diagram-label tone-${label.tone ?? "ink"}`} key={label.title}><strong>{label.title}</strong><span>{label.detail}</span></div>)}</div>
    </div>
    </div>
    <p className="diagram-explanation" aria-live="polite">{content.notes[mode]}</p>
    <figcaption>그림 {{ conversation: 1, adapter: 2, inspection: 3, age: 4, memory: 5 }[kind]}. {caption}</figcaption>
  </figure>;
}
