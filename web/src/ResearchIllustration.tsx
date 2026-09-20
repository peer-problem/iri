import { useEffect, useRef, useState } from "react";
import type { IllustrationKind } from "./research-scene";

const descriptions: Record<IllustrationKind, string> = {
  conversation: "입체 마이크와 전사문, 음성 답변 말풍선",
  adapter: "기본 모델 위에 결합하는 QLoRA 어댑터",
  inspection: "질문과 답변을 검토하는 검사 단계",
  age: "두 연령대의 어휘와 설명 수준을 나타내는 책과 말풍선",
  memory: "최근 여섯 턴을 나타내는 기록과 한 시간 보관 시계",
};

export function ResearchIllustration({ kind, caption, paused = false }: { kind: IllustrationKind; caption: string; paused?: boolean }) {
  const host = useRef<HTMLDivElement>(null);
  const pausedRef = useRef(paused);
  const resumeRef = useRef<(() => void) | null>(null);
  const [ready, setReady] = useState(false);
  useEffect(() => { pausedRef.current = paused; resumeRef.current?.(); }, [paused]);

  useEffect(() => {
    const container = host.current;
    if (!container) return;
    let disposed = false;
    let visible = false;
    let loading = false;
    let lost = false;
    let frame = 0;
    let previous = 0;
    let elapsed = 0;
    let scene: ReturnType<typeof import("./research-scene").createResearchScene> | undefined;
    const reduced = matchMedia("(prefers-reduced-motion: reduce)");
    setReady(false);
    const draw = (now: number) => {
      frame = 0;
      if (!scene || disposed || lost) return;
      if (previous) elapsed += Math.min((now - previous) / 1000, .06);
      previous = now;
      scene.render(elapsed);
      if (visible && !document.hidden && !reduced.matches && !pausedRef.current) frame = requestAnimationFrame(draw);
    };
    const resume = () => {
      cancelAnimationFrame(frame);
      previous = 0;
      if (scene && visible && !document.hidden && !lost) {
        if (reduced.matches || pausedRef.current) scene.render(elapsed);
        else frame = requestAnimationFrame(draw);
      }
    };
    const contextLost = (event: Event) => {
      event.preventDefault();
      lost = true;
      cancelAnimationFrame(frame);
      setReady(false);
    };
    const start = async () => {
      if (loading || scene || disposed) return;
      loading = true;
      try {
        const { createResearchScene } = await import("./research-scene");
        if (disposed) return;
        scene = createResearchScene(container, kind);
        scene.canvas.addEventListener("webglcontextlost", contextLost);
        scene.render(0);
        setReady(true);
        resume();
      } catch {
        // Preserve the static illustration if WebGL is unavailable.
        if (!disposed) setReady(false);
      }
    };
    const visibility = new IntersectionObserver(entries => {
      visible = entries[0].isIntersecting;
      if (visible) void start();
      resume();
    }, { rootMargin: "80px" });
    visibility.observe(container);
    const resize = new ResizeObserver(() => scene?.resize());
    resize.observe(container);
    document.addEventListener("visibilitychange", resume);
    reduced.addEventListener("change", resume);
    resumeRef.current = resume;
    return () => {
      disposed = true;
      cancelAnimationFrame(frame);
      visibility.disconnect();
      resize.disconnect();
      document.removeEventListener("visibilitychange", resume);
      reduced.removeEventListener("change", resume);
      resumeRef.current = null;
      scene?.canvas.removeEventListener("webglcontextlost", contextLost);
      scene?.dispose();
    };
  }, [kind]);

  return <figure className={`paper-figure illustration-${kind}`}>
    <div className={`research-illustration ${ready ? "is-rendered" : ""}`} role="img" aria-label={descriptions[kind]}>
      <div className="illustration-fallback" aria-hidden="true"><IllustrationFallback kind={kind} /></div>
      <div className="illustration-canvas" ref={host} aria-hidden="true" />
      {kind === "adapter" && <div className="scene-labels"><span>IRI v5 QLoRA</span><span>Kanana 2 3B</span></div>}
      {kind === "age" && <div className="age-labels"><span>4~6세</span><span>7~10세</span></div>}
    </div>
    <figcaption>{caption}</figcaption>
  </figure>;
}

function IllustrationFallback({ kind }: { kind: IllustrationKind }) {
  if (kind !== "conversation" && kind !== "adapter") return (
    <svg viewBox="0 0 620 180">
      {kind === "inspection" ? <g><rect x="160" y="40" width="65" height="95" rx="4" fill="#c8def1" /><path d="m310 28 48 18v38q0 35-48 55-48-20-48-55V46Z" fill="#8dbda4" /><circle cx="307" cy="77" r="17" fill="none" stroke="white" strokeWidth="4" /><path d="m319 90 17 17" stroke="white" strokeWidth="5" /><rect x="395" y="40" width="65" height="95" rx="4" fill="#ffedaa" /></g> : kind === "age" ? <g><rect x="160" y="43" width="90" height="110" rx="6" fill="#ed9d89" /><rect x="358" y="25" width="98" height="128" rx="6" fill="#79acd9" /><path d="M180 72h48m-48 16h35m145-31h58m-58 16h40" stroke="white" strokeWidth="4" /></g> : <g>{["#79acd9", "#ffedaa", "#ed9d89", "#8dbda4", "#b8a0d8", "#c8def1"].map((color, i) => <rect key={color} x={135 + i * 25} y={55 - i * 3} width="65" height="90" rx="6" fill={color} />)}<circle cx="418" cy="89" r="48" fill="#fffaf2" stroke="#c5beb2" strokeWidth="7" /><path d="M418 57v32l22 14" fill="none" stroke="#627486" strokeWidth="4" /></g>}
    </svg>
  );
  return (
    <>
      {kind === "conversation" ? (
        <svg viewBox="0 0 620 160" role="img" aria-label="마이크, 전사문, 답변 말풍선의 컬러 삽화">
          <path className="illustration-connection" d="M135 83H237M377 83H474" />
          <g className="illustration-mic">
            <ellipse cx="103" cy="135" rx="40" ry="5" fill="#e9edf2" />
            <path d="M103 107v22m-18 0h36" stroke="#566875" strokeWidth="3" strokeLinecap="round" />
            <rect x="81" y="26" width="44" height="70" rx="22" fill="#a9c7e7" stroke="#526b87" strokeWidth="1.2" />
            <path d="M71 75v9a32 32 0 0 0 64 0v-9" fill="none" stroke="#526b87" strokeWidth="2" strokeLinecap="round" />
            <path d="M93 45h20m-20 9h20m-20 9h20" stroke="#fff" strokeWidth="2" strokeLinecap="round" />
            <path className="mic-wave wave-one" d="M147 52q12 17 0 34" fill="none" stroke="#9bbad7" strokeWidth="2" strokeLinecap="round" />
            <path className="mic-wave wave-two" d="M159 44q18 25 0 50" fill="none" stroke="#c5d8e9" strokeWidth="2" strokeLinecap="round" />
          </g>
          <g className="illustration-page">
            <path d="M255 28h104l9 108H246Z" fill="#eef0eb" />
            <rect x="252" y="20" width="105" height="110" rx="3" fill="#fff6cf" stroke="#bcae76" strokeWidth="1.2" />
            <path d="M268 43h60" stroke="#bba457" strokeWidth="3" strokeLinecap="round" />
            <g className="transcript-lines" stroke="#c7b77e" strokeWidth="2" strokeLinecap="round"><path d="M268 62h69" /><path d="M268 75h55" /><path d="M268 88h64" /></g>
            <circle cx="338" cy="116" r="14" fill="#accdb6" stroke="#628570" />
            <path d="m332 116 4 4 8-9" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </g>
          <g className="illustration-bubble">
            <path d="M470 39h78q18 0 18 18v36q0 18-18 18h-38l-18 16v-16h-22q-18 0-18-18V57q0-18 18-18Z" fill="#f1b5a6" stroke="#bb7b6c" strokeWidth="1.2" />
            <g className="speech-bars" stroke="#fff" strokeWidth="5" strokeLinecap="round"><path d="M484 69v13" /><path d="M496 60v31" /><path d="M508 65v21" /><path d="M520 55v41" /><path d="M532 68v15" /></g>
          </g>
        </svg>
      ) : (
        <svg viewBox="0 0 620 170" role="img" aria-label="청색 기본 모델 층 위에 보라색 어댑터 층을 적용한 컬러 삽화">
          <ellipse cx="307" cy="146" rx="96" ry="8" fill="#edf0f4" />
          <g className="model-layers" stroke="#6f91b4" strokeWidth="1.1" strokeLinejoin="round">
            <path d="m222 111 84-29 85 29-85 30Z" fill="#adc7e0" /><path d="m222 111 84 30 85-30v9l-85 30-84-30Z" fill="#8baed0" />
            <path d="m222 89 84-29 85 29-85 30Z" fill="#c4d8eb" /><path d="m222 89 84 30 85-30v9l-85 30-84-30Z" fill="#9dbbd8" />
            <path d="m222 67 84-29 85 29-85 30Z" fill="#d9e6f2" /><path d="m222 67 84 30 85-30v9l-85 30-84-30Z" fill="#adc7e0" />
          </g>
          <g className="adapter-layer" stroke="#9b85b4" strokeWidth="1.1" strokeLinejoin="round"><path d="m253 32 53-18 54 18-54 19Z" fill="#deceed" /><path d="m253 32 53 19 54-19v7l-54 19-53-19Z" fill="#bfa5d8" /><path d="m282 32 24-8 25 8-25 9Z" fill="#f7f1fc" /></g>
          <g className="illustration-labels" fill="#555" fontSize="13"><text x="432" y="39">IRI v5 QLoRA</text><text x="432" y="113">Kanana 2 3B</text></g>
          <g fill="none" stroke="#b9bec6" strokeWidth="1"><path d="M361 32h53" /><path d="M393 108h21" /></g>
          <g className="adapter-particles" fill="#c4acdc"><circle cx="263" cy="65" r="2" /><circle cx="304" cy="70" r="2" /><circle cx="346" cy="62" r="2" /></g>
        </svg>
      )}
    </>
  );
}
