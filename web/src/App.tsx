import { useEffect, useRef, useState } from "react";
import { Button } from "@base-ui/react/button";
import { Dialog } from "@base-ui/react/dialog";
import { Input } from "@base-ui/react/input";
import { Switch } from "@base-ui/react/switch";
import { Radio } from "@base-ui/react/radio";
import { RadioGroup } from "@base-ui/react/radio-group";
import {
  ArrowUp,
  ArrowUpRight,
  AudioLines,
  Check,
  Keyboard,
  LogOut,
  Mic,
  Plus,
  Settings2,
  ShieldCheck,
  Square,
  Volume2,
  X,
} from "lucide-react";
import { ApiError, jsonRequest, request } from "./api";

type Phase =
  | "idle"
  | "acquiring"
  | "recording"
  | "transcribing"
  | "thinking"
  | "synthesizing"
  | "speaking";
type Message = { id: string; role: "user" | "assistant"; text: string };
const suggestions = [
  "하늘은 왜 파란색이야?",
  "공룡에 대해 알려줘",
  "친구랑 다퉜을 땐 어떻게 해?",
];
const labels: Record<Phase, string> = {
  idle: "이야기할 준비가 됐어요",
  acquiring: "마이크 사용 권한을 기다리고 있어요",
  recording: "듣고 있어요",
  transcribing: "이야기를 글로 옮기고 있어요",
  thinking: "답변을 생각하고 있어요",
  synthesizing: "목소리를 준비하고 있어요",
  speaking: "이리의 이야기를 들어보세요",
};

export default function App() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [code, setCode] = useState("");
  const [loginBusy, setLoginBusy] = useState(false);
  const [loginError, setLoginError] = useState("");
  const [age, setAge] = useState("4-6");
  const [autoRead, setAutoRead] = useState(true);
  const [consented, setConsented] = useState(false);
  const [consentOpen, setConsentOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [phase, setPhase] = useState<Phase>("idle");
  const [draft, setDraft] = useState("");
  const [transcript, setTranscript] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [error, setError] = useState("");
  const [seconds, setSeconds] = useState(0);
  const [level, setLevel] = useState(0);
  const recorder = useRef<MediaRecorder | null>(null);
  const recordingAttempt = useRef(0);
  const stream = useRef<MediaStream | null>(null);
  const audio = useRef<HTMLAudioElement | null>(null);
  const playbackContext = useRef<AudioContext | null>(null);
  const playbackSource = useRef<AudioBufferSourceNode | null>(null);
  const audioClips = useRef(
    new Map<string, { bytes: ArrayBuffer; url: string }>(),
  );
  const audioContext = useRef<AudioContext | null>(null);
  const frame = useRef(0);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const controller = useRef<AbortController | null>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const log = useRef<HTMLDivElement>(null);
  const busy = phase !== "idle" && phase !== "speaking";

  useEffect(() => {
    request("/session")
      .then(async () => {
        const response = await request("/conversation");
        const saved = await response.json();
        setAge(saved.age_band);
        setMessages(
          saved.messages.map(
            (m: {
              id: string;
              role: "user" | "assistant";
              content: string;
            }) => ({ id: m.id, role: m.role, text: m.content }),
          ),
        );
        setAuthenticated(true);
      })
      .catch(() => setAuthenticated(false));
    return () => {
      cancelRecording();
      stopPlayback();
      controller.current?.abort();
      clearAudio();
      void playbackContext.current?.close();
      playbackContext.current = null;
    };
  }, []);
  useEffect(() => {
    log.current?.scrollTo({
      top: log.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, phase]);

  function clearAudio() {
    audioClips.current.forEach(({ url }) => URL.revokeObjectURL(url));
    audioClips.current.clear();
  }
  function cancelRecording() {
    recordingAttempt.current++;
    const rec = recorder.current;
    recorder.current = null;
    if (rec) {
      rec.onstop = null;
      rec.onerror = null;
      rec.ondataavailable = null;
      if (rec.state !== "inactive") rec.stop();
    }
    releaseMic();
  }
  function releaseMic() {
    if (timer.current) clearInterval(timer.current);
    cancelAnimationFrame(frame.current);
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    if (audioContext.current?.state !== "closed")
      void audioContext.current?.close();
    audioContext.current = null;
  }
  function stopPlayback() {
    if (playbackSource.current) {
      playbackSource.current.onended = null;
      playbackSource.current.stop();
      playbackSource.current.disconnect();
      playbackSource.current = null;
    }
    audio.current?.pause();
    audio.current = null;
  }
  function preparePlayback() {
    // Safari requires the audio context to start while the send/listen gesture is active.
    try {
      const context = playbackContext.current ?? new AudioContext();
      playbackContext.current = context;
      if (context.state === "suspended") void context.resume().catch(() => {});
      const silent = context.createBufferSource();
      silent.buffer = context.createBuffer(1, 1, context.sampleRate);
      silent.connect(context.destination);
      silent.onended = () => silent.disconnect();
      silent.start();
    } catch {
      // A directly clicked replay can still use the media-element path below.
    }
  }
  function fail(e: unknown) {
    if (e instanceof ApiError && e.status === 401) {
      setAuthenticated(false);
      setMessages([]);
      clearAudio();
    }
    setError(
      e instanceof ApiError
        ? e.message
        : "연결을 확인한 뒤 다시 시도해 주세요.",
    );
    setPhase("idle");
  }
  async function login(e: React.FormEvent) {
    e.preventDefault();
    setLoginBusy(true);
    setLoginError("");
    try {
      await jsonRequest("/session", { code });
      setAuthenticated(true);
      setCode("");
      setError("");
    } catch (e) {
      setLoginError(
        e instanceof ApiError && e.status === 401
          ? "참여 코드가 맞는지 확인해 주세요."
          : "잠시 후 다시 시도해 주세요.",
      );
    } finally {
      setLoginBusy(false);
    }
  }
  async function newConversation(nextAge?: string) {
    if (busy) return;
    stopPlayback();
    setPhase("idle");
    try {
      await request("/conversation", { method: "DELETE" });
      setMessages([]);
      setDraft("");
      setTranscript(false);
      setError("");
      clearAudio();
      if (nextAge) setAge(nextAge);
    } catch (e) {
      fail(e);
    }
  }
  async function logout() {
    try {
      await request("/session", { method: "DELETE" });
    } catch (e) {
      if (!(e instanceof ApiError && e.status === 401)) {
        fail(e);
        return;
      }
    }
    stopPlayback();
    clearAudio();
    setMessages([]);
    setDraft("");
    setAuthenticated(false);
    setSettingsOpen(false);
    setPhase("idle");
  }
  async function speak(message: Message, userGesture = false) {
    if (userGesture) preparePlayback();
    stopPlayback();
    setError("");
    setPhase("synthesizing");
    try {
      let clip = audioClips.current.get(message.id);
      if (!clip) {
        const response = await jsonRequest("/speech", { text: message.text });
        const bytes = await response.arrayBuffer();
        clip = {
          bytes,
          url: URL.createObjectURL(new Blob([bytes], { type: "audio/mpeg" })),
        };
        audioClips.current.set(message.id, clip);
        if (audioClips.current.size > 12) {
          const oldest = audioClips.current.keys().next().value!;
          URL.revokeObjectURL(audioClips.current.get(oldest)!.url);
          audioClips.current.delete(oldest);
        }
      }
      const context = playbackContext.current;
      if (context?.state === "running") {
        try {
          const buffer = await context.decodeAudioData(clip.bytes.slice(0));
          const source = context.createBufferSource();
          source.buffer = buffer;
          source.connect(context.destination);
          playbackSource.current = source;
          source.onended = () => {
            if (playbackSource.current === source) {
              playbackSource.current = null;
              source.disconnect();
              setPhase("idle");
            }
          };
          source.start();
          setPhase("speaking");
          return;
        } catch {
          // Keep the existing replay path if decoding is unavailable.
        }
      }
      const player = new Audio(clip.url);
      audio.current = player;
      player.onended = () => setPhase("idle");
      player.onerror = () => {
        setPhase("idle");
        setError("음성을 재생하지 못했어요. 답변 듣기를 다시 눌러 주세요.");
      };
      try {
        await player.play();
        setPhase("speaking");
      } catch {
        setPhase("idle");
        setError("답변 듣기를 누르면 목소리를 들을 수 있어요.");
      }
    } catch (e) {
      fail(e);
      if (!(e instanceof ApiError && e.status === 401)) {
        setError(
          "답변은 준비됐지만 음성 연결이 어려워요. 잠시 후 답변 듣기를 눌러 주세요.",
        );
      }
    }
  }
  async function send(e?: React.FormEvent) {
    e?.preventDefault();
    if (!draft.trim() || busy) return;
    const question = draft.trim();
    if (autoRead) preparePlayback();
    stopPlayback();
    setPhase("thinking");
    setError("");
    controller.current = new AbortController();
    try {
      const response = await jsonRequest(
        "/chat",
        { message: question, age_band: age },
        AbortSignal.any([
          controller.current.signal,
          AbortSignal.timeout(95_000),
        ]),
      );
      const result = await response.json();
      const answer: Message = {
        id: result.request_id,
        role: "assistant",
        text: result.answer,
      };
      setMessages((m) =>
        [
          ...m,
          { id: crypto.randomUUID(), role: "user" as const, text: question },
          answer,
        ].slice(-12),
      );
      setDraft("");
      setTranscript(false);
      setPhase("idle");
      if (autoRead) await speak(answer);
    } catch (e) {
      fail(e);
    }
  }
  async function startRecording(consentGranted = false) {
    if (busy) return;
    if (!consented && !consentGranted) {
      setConsentOpen(true);
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setError(
        "이 브라우저에서는 마이크를 사용할 수 없어요. 글로 입력하거나 최신 Chrome 또는 Safari를 사용해 주세요.",
      );
      return;
    }
    stopPlayback();
    setError("");
    setSeconds(0);
    const attempt = ++recordingAttempt.current;
    setPhase("acquiring");
    try {
      const media = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      });
      // A permission prompt can resolve after cancellation or unmount.
      if (attempt !== recordingAttempt.current) {
        media.getTracks().forEach((track) => track.stop());
        return;
      }
      stream.current = media;
      const mime = ["audio/webm;codecs=opus", "audio/mp4", "audio/webm"].find(
        (t) => MediaRecorder.isTypeSupported(t),
      );
      if (!mime) throw new Error("unsupported");
      const rec = new MediaRecorder(media, {
        mimeType: mime,
        audioBitsPerSecond: 64_000,
      });
      recorder.current = rec;
      const chunks: Blob[] = [];
      rec.ondataavailable = (e) => {
        if (e.data.size) chunks.push(e.data);
      };
      rec.onerror = () => {
        cancelRecording();
        setLevel(0);
        setPhase("idle");
        setError("녹음하지 못했어요. 마이크 연결을 확인해 주세요.");
      };
      rec.onstop = async () => {
        releaseMic();
        recorder.current = null;
        setLevel(0);
        const blob = new Blob(chunks, { type: mime.split(";")[0] });
        if (blob.size < 100) {
          setPhase("idle");
          setError("목소리가 녹음되지 않았어요. 다시 이야기해 주세요.");
          return;
        }
        setPhase("transcribing");
        try {
          const response = await request("/transcribe", {
            method: "POST",
            headers: { "Content-Type": blob.type, "X-Audio-Consent": "true" },
            body: blob,
          });
          const result = await response.json();
          setDraft(result.text);
          setTranscript(true);
          setPhase("idle");
          setTimeout(() => textarea.current?.focus(), 0);
        } catch (e) {
          fail(e);
        }
      };
      rec.start(250);
      setPhase("recording");
      let elapsed = 0;
      timer.current = setInterval(() => {
        elapsed++;
        setSeconds(elapsed);
        if (elapsed >= 60 && rec.state === "recording") rec.stop();
      }, 1000);
      try {
        const context = new AudioContext();
        audioContext.current = context;
        const analyser = context.createAnalyser();
        analyser.fftSize = 256;
        context.createMediaStreamSource(media).connect(analyser);
        const data = new Uint8Array(analyser.frequencyBinCount);
        const draw = () => {
          analyser.getByteFrequencyData(data);
          setLevel(data.reduce((a, b) => a + b, 0) / data.length / 128);
          frame.current = requestAnimationFrame(draw);
        };
        draw();
      } catch {
        /* Recording still works when visual metering is unavailable. */
      }
    } catch (e) {
      if (attempt !== recordingAttempt.current) return;
      cancelRecording();
      setPhase("idle");
      setError(
        e instanceof DOMException && e.name === "NotAllowedError"
          ? "마이크 권한이 꺼져 있어요. 주소창에서 허용하거나 글로 입력해 주세요."
          : "마이크를 연결하지 못했어요. 글로도 이야기할 수 있어요.",
      );
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="대화 메뉴">
        <a href="/" className="brand" aria-label="이리 홈">
          iri
          <span className="brand-mark" aria-hidden="true">
            ↗
          </span>
        </a>
        <p className="brand-caption">함께 나누는 작은 궁금증</p>
        <Button
          className="button new-chat"
          onClick={() => void newConversation()}
          disabled={busy || !authenticated}
        >
          <Plus />새 이야기
        </Button>
        <div className="sidebar-body">
          <span className="section-label">지금 나누는 이야기</span>
          <div className="current-chat">
            <AudioLines />
            <span>
              {messages.length ? messages[0].text : "이리와 이야기하기"}
            </span>
          </div>
        </div>
        <div className="sidebar-note">
          <ShieldCheck />
          <p>
            아이와 보호자가
            <br />
            함께 사용하는 대화 공간
          </p>
        </div>
        <div className="sidebar-bottom">
          <span>IRI DEMO</span>
          <span>01</span>
        </div>
      </aside>
      <main className="workspace">
        <header className="topbar">
          <span className="mobile-brand">iri</span>
          <span>이리와 이야기하기</span>
          <div className="topbar-actions">
            <span className="age-label">{age.replace("-", "~")}세</span>
            <Button
              className="icon-button mobile-new"
              aria-label="새 이야기"
              disabled={busy || !authenticated}
              onClick={() => void newConversation()}
            >
              <Plus />
            </Button>
            <Button
              className="icon-button"
              aria-label="대화 설정"
              onClick={() => setSettingsOpen(true)}
            >
              <Settings2 />
            </Button>
          </div>
        </header>
        <div className="conversation" ref={log}>
          {messages.length === 0 ? (
            <section className="welcome">
              <span className="welcome-symbol" aria-hidden="true">
                <AudioLines />
              </span>
              <h1>무엇이 궁금해?</h1>
              <p>
                버튼을 누르고 편하게 이야기해 줘.
                <br />
                이리가 듣고 함께 생각해 볼게.
              </p>
              <div className="suggestions" aria-label="이야기 예시">
                {suggestions.map((s) => (
                  <Button
                    key={s}
                    className="suggestion"
                    disabled={busy}
                    onClick={() => {
                      setDraft(s);
                      setTranscript(false);
                      textarea.current?.focus();
                    }}
                  >
                    {s}
                    <ArrowUpRight />
                  </Button>
                ))}
              </div>
            </section>
          ) : (
            <div
              className="message-log"
              role="log"
              aria-label="대화 내용"
              aria-live="polite"
            >
              {messages.map((message) => (
                <article className={`message ${message.role}`} key={message.id}>
                  <div className="message-author">
                    {message.role === "user" ? "나" : "이리"}
                  </div>
                  <div className="message-content">
                    <p>{message.text}</p>
                    {message.role === "assistant" && (
                      <Button
                        className="text-button"
                        disabled={busy}
                        onClick={() => void speak(message, true)}
                      >
                        <Volume2 />
                        답변 듣기
                      </Button>
                    )}
                  </div>
                </article>
              ))}
            </div>
          )}
          {(phase === "thinking" || phase === "synthesizing") && (
            <p className="thinking" role="status">
              {labels[phase]}
            </p>
          )}
        </div>
        <section className="voice-dock" aria-label="음성 및 텍스트 입력">
          <div className="voice-status">
            <div className="waveform" aria-hidden="true">
              {Array.from({ length: 25 }, (_, i) => (
                <span
                  key={i}
                  style={{
                    height: `${phase === "recording" ? 4 + (Math.sin(i * 1.7) * 0.5 + 0.5) * level * 44 : 4 + Math.max(0, 1 - Math.abs(i - 12) / 12) * 12}px`,
                  }}
                />
              ))}
            </div>
            <p role="status">
              {labels[phase]}
              {phase === "recording" && (
                <span className="record-time">
                  {" "}
                  {String(seconds).padStart(2, "0")} / 60초
                </span>
              )}
            </p>
          </div>
          <div className="voice-actions">
            {phase === "speaking" ? (
              <Button
                className="button primary record-button"
                onClick={() => {
                  stopPlayback();
                  setPhase("idle");
                }}
              >
                <Square />
                듣기 멈추기
              </Button>
            ) : (
              <Button
                className="button primary record-button"
                disabled={
                  !authenticated ||
                  (busy && phase !== "recording" && phase !== "acquiring")
                }
                onClick={() => {
                  if (phase === "acquiring") {
                    cancelRecording();
                    setPhase("idle");
                  } else if (phase === "recording") {
                    if (recorder.current?.state === "recording")
                      recorder.current.stop();
                  } else void startRecording();
                }}
              >
                {phase === "acquiring" ? (
                  <X />
                ) : phase === "recording" ? (
                  <Square />
                ) : (
                  <Mic />
                )}
                {phase === "acquiring"
                  ? "마이크 연결 취소"
                  : phase === "recording"
                    ? "말하기 마치기"
                    : "눌러서 이야기하기"}
              </Button>
            )}
          </div>
          {error && (
            <div className="error" role="alert">
              <span>{error}</span>
              <Button
                className="icon-button"
                aria-label="안내 닫기"
                onClick={() => setError("")}
              >
                <X />
              </Button>
            </div>
          )}
          <form className="composer" onSubmit={send}>
            <label htmlFor="message">
              <Keyboard />
              {transcript
                ? "이렇게 들었어요. 맞는지 확인해 주세요."
                : "글로도 이야기할 수 있어요"}
            </label>
            <div className="input-row">
              <textarea
                ref={textarea}
                id="message"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="궁금한 것을 적어 주세요"
                maxLength={1000}
                rows={2}
                disabled={busy}
                onKeyDown={(e) => {
                  if (
                    e.key === "Enter" &&
                    !e.shiftKey &&
                    !e.nativeEvent.isComposing
                  ) {
                    e.preventDefault();
                    void send();
                  }
                }}
              />
              <Button
                className="button primary send-button"
                type="submit"
                disabled={busy || !draft.trim() || !authenticated}
                aria-label={transcript ? "확인하고 보내기" : "보내기"}
              >
                {transcript ? <Check /> : <ArrowUp />}
              </Button>
            </div>
            <div className="composer-footer">
              <span>
                {transcript
                  ? "다르게 들렸다면 글을 고쳐서 보내 주세요."
                  : "Enter로 보내기 / Shift + Enter로 줄바꿈"}
              </span>
              <span>{draft.length}/1000</span>
            </div>
          </form>
          <p className="disclosure">
            이리의 목소리는 AI가 만들어요. 중요한 내용은 보호자와 함께 확인해
            주세요.
          </p>
        </section>
      </main>
      <Dialog.Root open={authenticated === false} onOpenChange={() => {}}>
        <Dialog.Portal>
          <Dialog.Backdrop className="backdrop" />
          <Dialog.Popup className="popup">
            <Dialog.Title className="dialog-title">
              이리와 이야기 시작하기
            </Dialog.Title>
            <Dialog.Description className="dialog-description">
              보호자와 함께 참여 코드를 입력해 주세요.
            </Dialog.Description>
            <form onSubmit={login}>
              <label className="field-label" htmlFor="access-code">
                참여 코드
              </label>
              <Input
                id="access-code"
                className="input"
                type="password"
                autoComplete="current-password"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                required
                aria-invalid={!!loginError}
                aria-describedby={loginError ? "login-error" : undefined}
              />
              {loginError && (
                <p id="login-error" className="error-text" role="alert">
                  {loginError}
                </p>
              )}
              <p className="dialog-description privacy-note">
                대화는 최대 1시간 동안 서버 메모리에만 머물며, 새 이야기를
                시작하거나 나가면 지워져요. 음성과 질문은 답변을 위해 외부 AI
                서비스에서 처리돼요.
              </p>
              <Button
                className="button primary full-width"
                type="submit"
                disabled={loginBusy || !code}
              >
                {loginBusy ? "확인하고 있어요" : "시작하기"}
              </Button>
            </form>
          </Dialog.Popup>
        </Dialog.Portal>
      </Dialog.Root>
      <Dialog.Root open={consentOpen} onOpenChange={setConsentOpen}>
        <Dialog.Portal>
          <Dialog.Backdrop className="backdrop" />
          <Dialog.Popup className="popup">
            <Dialog.Title className="dialog-title">
              목소리로 이야기해 볼까요?
            </Dialog.Title>
            <Dialog.Description className="dialog-description">
              녹음한 음성은 글로 바꾸기 위해 OpenAI에 전송돼요. 이리 서버에는
              녹음 파일을 저장하지 않아요. 보호자와 함께 확인해 주세요.
            </Dialog.Description>
            <div className="dialog-actions">
              <Dialog.Close className="button">글로 이야기하기</Dialog.Close>
              <Button
                className="button primary"
                onClick={() => {
                  setConsented(true);
                  setConsentOpen(false);
                  void startRecording(true);
                }}
              >
                동의하기
              </Button>
            </div>
          </Dialog.Popup>
        </Dialog.Portal>
      </Dialog.Root>
      <Dialog.Root open={settingsOpen} onOpenChange={setSettingsOpen}>
        <Dialog.Portal>
          <Dialog.Backdrop className="backdrop" />
          <Dialog.Popup className="popup">
            <div className="dialog-heading">
              <Dialog.Title className="dialog-title">대화 설정</Dialog.Title>
              <Dialog.Close className="icon-button" aria-label="설정 닫기">
                <X />
              </Dialog.Close>
            </div>
            <Dialog.Description className="dialog-description">
              아이의 나이에 맞춰 쉽게 설명해요.
            </Dialog.Description>
            <RadioGroup
              value={age}
              onValueChange={(value) => void newConversation(String(value))}
              disabled={busy || !authenticated}
              aria-labelledby="age-title"
              className="radio-group"
            >
              <span id="age-title" className="field-label">
                아이 나이
              </span>
              {["4-6", "7-10"].map((a) => (
                <label className="radio-label" key={a}>
                  <Radio.Root value={a} className="radio">
                    <Radio.Indicator className="radio-indicator" />
                  </Radio.Root>
                  {a.replace("-", "~")}세
                </label>
              ))}
            </RadioGroup>
            <p className="dialog-description">
              나이를 바꾸면 새로운 이야기가 시작돼요.
            </p>
            <label className="switch-label">
              <span>답변을 목소리로 들려주기</span>
              <Switch.Root
                className="switch"
                checked={autoRead}
                onCheckedChange={setAutoRead}
              >
                <Switch.Thumb className="thumb" />
              </Switch.Root>
            </label>
            <p className="dialog-description">
              꺼 두어도 모든 답변을 글로 볼 수 있어요.
            </p>
            <div className="settings-footer">
              <Button
                className="text-button"
                onClick={() => void logout()}
                disabled={busy || !authenticated}
              >
                <LogOut />
                대화 지우고 나가기
              </Button>
            </div>
          </Dialog.Popup>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
