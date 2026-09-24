import { useEffect, useRef, useState } from "react";
import { InputMeter } from "./InputMeter";
import { LiquidButtons } from "./LiquidButtons";
import { Orb } from "./Orb";
import { providerLabel } from "./provider";
import {
  phaseLabels,
  useVoiceConversation,
} from "./useVoiceConversation";

function SparkIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z" />
    </svg>
  );
}

function StopIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="6" y="6" width="12" height="12" rx="2" />
    </svg>
  );
}

function VolumeIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 9v6h4l5 4V5L9 9H5Z" />
      <path d="M17 9.5a4 4 0 0 1 0 5M19.5 7a7.5 7.5 0 0 1 0 10" />
    </svg>
  );
}

function KeyboardIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3" y="6" width="18" height="12" rx="2" />
      <path d="M7 10h.01M10 10h.01M13 10h.01M16 10h.01M7 14h2M11 14h6" />
    </svg>
  );
}

function SettingsIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <path d="M12 3v2.2M12 18.8V21M3 12h2.2M18.8 12H21M5.6 5.6l1.6 1.6M16.8 16.8l1.6 1.6M18.4 5.6l-1.6 1.6M7.2 16.8l-1.6 1.6" />
    </svg>
  );
}

function HistoryIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 5h16M4 12h16M4 19h10" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 6v12M6 12h12" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m6 6 12 12M18 6 6 18" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 19V5M6 11l6-6 6 6" />
    </svg>
  );
}

const invitations = [
  "구를 눌러 말을 걸어보세요.",
  "무엇이 궁금해?",
  "오늘 무슨 일이 있었어?",
  "좋아하는 걸 이야기해 볼래?",
  "신기한 걸 물어봐도 좋아.",
];

export default function App() {
  const voice = useVoiceConversation();
  const selection = useRef(0);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const settingsAnchor = useRef<HTMLDivElement>(null);
  const [settingsClosing, setSettingsClosing] = useState(false);
  const [shapeIndex, setShapeIndex] = useState(0);
  const [composerOpen, setComposerOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [invitationIndex, setInvitationIndex] = useState(0);
  const invitationIndexRef = useRef(0);
  const showingInvitation =
    voice.phase !== "recording" &&
    voice.phase !== "acquiring" &&
    !voice.busy &&
    !voice.error;
  const shapeLabels = [
    "육면체 꺼내기",
    "삼각형 꺼내기",
    "기린 꺼내기",
    "구로 되돌리기",
  ];

  useEffect(() => {
    document.title = "IRI | 함께 나누는 이야기";
  }, []);

  useEffect(() => {
    if (!showingInvitation) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const id = window.setInterval(() => {
      invitationIndexRef.current = (invitationIndexRef.current + 1) % invitations.length;
      setInvitationIndex(invitationIndexRef.current);
    }, 5000);
    return () => window.clearInterval(id);
  }, [showingInvitation]);

  useEffect(() => {
    if (!voice.settingsOpen || settingsClosing) return;
    const closeFromOutside = (event: PointerEvent) => {
      if (!settingsAnchor.current?.contains(event.target as Node)) {
        setSettingsClosing(true);
      }
    };
    const closeFromEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSettingsClosing(true);
    };
    document.addEventListener("pointerdown", closeFromOutside);
    document.addEventListener("keydown", closeFromEscape);
    return () => {
      document.removeEventListener("pointerdown", closeFromOutside);
      document.removeEventListener("keydown", closeFromEscape);
    };
  }, [voice.settingsOpen, settingsClosing]);

  useEffect(() => {
    if (voice.transcript) {
      setComposerOpen(true);
      window.setTimeout(() => textarea.current?.focus(), 0);
    }
  }, [voice.transcript]);

  useEffect(() => {
    const field = textarea.current;
    if (!field || !composerOpen) return;
    field.style.height = "0px";
    field.style.height = `${field.scrollHeight}px`;
  }, [composerOpen, voice.draft]);

  const toggleMicrophone = () => {
    if (voice.phase === "acquiring") {
      voice.cancelMicRequest();
    } else if (voice.phase === "recording") {
      voice.finishRecording();
    } else {
      void voice.startRecording();
    }
  };

  const microphoneLabel =
    voice.phase === "acquiring"
      ? "마이크 연결 취소"
      : voice.phase === "recording"
        ? "말하기 마치기"
        : "구를 눌러 말을 걸어보세요.";

  const closeHistory = () => {
    if (voice.playbackMessageId) voice.stopSpeaking();
    setHistoryOpen(false);
  };

  const submitComposer = async () => {
    if (await voice.send()) setComposerOpen(false);
  };

  return (
    <main className="orb-app" data-phase={voice.phase}>
      <a className="iri-brand" href="/" aria-label="이리 홈">
        iri
        <span className="brand-star" aria-hidden="true">
          ✳
        </span>
      </a>

      <nav className="top-actions" aria-label="대화 메뉴">
        <span className="age-badge">{voice.age.replace("-", "~")}세</span>
        <button
          className="plain-icon"
          aria-label="대화 기록"
          onClick={() => setHistoryOpen(true)}
          disabled={!voice.messages.length}
        >
          <HistoryIcon />
        </button>
        <button
          className="plain-icon chip-icon"
          aria-label="새 이야기"
          disabled={voice.busy}
          onClick={() => void voice.newConversation()}
        >
          <PlusIcon />
        </button>
        <div className="menu-anchor" ref={settingsAnchor}>
          <button
            className="plain-icon chip-icon"
            aria-label="대화 설정"
            aria-expanded={voice.settingsOpen}
            onClick={() => {
              if (voice.settingsOpen) setSettingsClosing(true);
              else voice.setSettingsOpen(true);
            }}
          >
            <SettingsIcon />
          </button>
          {voice.settingsOpen && (
            <section
              className="menu-popover"
              data-closing={settingsClosing || undefined}
              role="dialog"
              aria-label="대화 설정"
              onAnimationEnd={(event) => {
                if (event.target !== event.currentTarget || !settingsClosing) return;
                setSettingsClosing(false);
                voice.setSettingsOpen(false);
              }}
            >
              <div className="overlay-heading">
                <h2>대화 설정</h2>
                <button
                  className="plain-icon"
                  onClick={() => setSettingsClosing(true)}
                  aria-label="닫기"
                >
                  <CloseIcon />
                </button>
              </div>
              <p className="overlay-description">아이의 나이에 맞춰 쉽게 설명해요.</p>
              <fieldset className="setting-group" aria-label="대화 연령">
                <div className="segmented-control">
                  {["4-6", "7-10"].map((value) => (
                    <button
                      type="button"
                      key={value}
                      aria-pressed={voice.age === value}
                      disabled={voice.busy}
                      onClick={() => void voice.newConversation(value)}
                    >
                      {value.replace("-", "~")}세
                    </button>
                  ))}
                </div>
              </fieldset>
              <label className="toggle-row">
                <span>답변을 목소리로 듣기</span>
                <input
                  type="checkbox"
                  checked={voice.autoRead}
                  onChange={(event) => voice.setAutoRead(event.target.checked)}
                />
              </label>
            </section>
          )}
        </div>
      </nav>

      <Orb
        signal={voice.signal}
        selection={selection}
        onActivate={toggleMicrophone}
        label={microphoneLabel}
        hint={voice.phase === "recording"
          ? "다 이야기했다면 구를 다시 눌러주세요"
          : voice.phase === "acquiring"
            ? "구를 누르면 마이크 연결을 취소해요"
            : voice.busy
              ? phaseLabels[voice.phase]
              : voice.error || invitations[invitationIndex]}
        announce={Boolean(voice.error) && !voice.busy && voice.phase !== "recording" && voice.phase !== "acquiring"}
        recording={voice.phase === "recording"}
        disabled={voice.busy && !["recording", "acquiring"].includes(voice.phase)}
      />

      {voice.latestAnswer && (
        <section className="answer-stage" aria-live="polite">
          {voice.latestUser && (
            <p className="last-question">{voice.latestUser.text}</p>
          )}
          <p className="last-answer">{voice.latestAnswer.text}</p>
        </section>
      )}

      <div className="voice-controls">
        {(voice.phase === "acquiring" || voice.phase === "speaking") && (
          <p className="voice-status" role="status">
            {phaseLabels[voice.phase]}
          </p>
        )}
        {voice.phase === "recording" && <InputMeter signal={voice.signal} />}
        <LiquidButtons>
          <button
            aria-label={shapeLabels[shapeIndex]}
            onClick={() => {
              selection.current += 1;
              setShapeIndex(selection.current % 4);
            }}
          >
            <SparkIcon />
          </button>
          <button
            aria-label={voice.phase === "speaking" ? "말하기 멈추기" : "답변 다시 듣기"}
            aria-pressed={voice.phase === "speaking"}
            disabled={!voice.latestAnswer || (voice.busy && voice.phase !== "speaking")}
            onClick={() => {
              if (voice.phase === "speaking") voice.stopSpeaking();
              else if (voice.latestAnswer) void voice.speak(voice.latestAnswer, true);
            }}
          >
            {voice.phase === "speaking" ? <StopIcon /> : <VolumeIcon />}
          </button>
          <button
            aria-label="글로 이야기하기"
            aria-pressed={composerOpen}
            onClick={() => {
              setComposerOpen((open) => !open);
              window.setTimeout(() => textarea.current?.focus(), 0);
            }}
            disabled={voice.busy}
          >
            <KeyboardIcon />
          </button>
        </LiquidButtons>
      </div>

      {composerOpen && (
        <form
          className="composer-sheet"
          onSubmit={(event) => {
            event.preventDefault();
            void submitComposer();
          }}
        >
          {voice.transcript && (
            <div className="composer-copy">
              <label htmlFor="message">이렇게 들었어요. 맞는지 확인해 주세요.</label>
            </div>
          )}
          <div className="composer-row">
            <textarea
              ref={textarea}
              id="message"
              value={voice.draft}
              onChange={(event) => voice.setDraft(event.target.value)}
              aria-label={voice.transcript ? undefined : "글로 이야기하기"}
              placeholder="궁금한 것을 말하거나 적어 주세요"
              maxLength={1000}
              rows={1}
              disabled={voice.busy}
              onKeyDown={(event) => {
                if (
                  event.key === "Enter" &&
                  !event.shiftKey &&
                  !event.nativeEvent.isComposing
                ) {
                  event.preventDefault();
                  void submitComposer();
                }
              }}
            />
            <button
              type="button"
              className="plain-icon sheet-close"
              aria-label="입력 닫기"
              onClick={() => {
                setComposerOpen(false);
                voice.setTranscript(false);
              }}
            >
              <CloseIcon />
            </button>
            <button
              className="send-button"
              type="submit"
              disabled={voice.busy || !voice.draft.trim()}
              aria-label="확인하고 보내기"
            >
              <SendIcon />
            </button>
          </div>
          {voice.transcript && (
            <p>다르게 들렸다면 문장을 고친 뒤 보내 주세요.</p>
          )}
        </form>
      )}

      {voice.latestAnswer?.provider && (
        <p className="powered">{providerLabel(voice.latestAnswer.provider)}</p>
      )}

      {historyOpen && (
        <div className="history-overlay" role="dialog" aria-modal="true">
          <div className="history-heading">
            <div>
              <span>지금까지 나눈 이야기</span>
              <small>{Math.floor(voice.messages.length / 2)}개의 대화</small>
            </div>
            <button
              className="plain-icon"
              aria-label="대화 기록 닫기"
              onClick={closeHistory}
            >
              <CloseIcon />
            </button>
          </div>
          <div className="history-list" role="log">
            {voice.messages.map((message) => {
              const active = voice.playbackMessageId === message.id;
              const preparing = active && voice.phase === "synthesizing";
              const speaking = active && voice.phase === "speaking";

              return (
                <article key={message.id} data-role={message.role}>
                  <span>{message.role === "user" ? "나" : "이리"}</span>
                  <div className="history-message">
                    <p>{message.text}</p>
                    {message.role === "assistant" && (
                      <button
                        className="history-replay"
                        data-active={active || undefined}
                        disabled={voice.busy && !active}
                        aria-label={
                          preparing
                            ? "이 답변 음성 준비 중지"
                            : speaking
                              ? "이 답변 재생 멈추기"
                              : "이 답변 듣기"
                        }
                        onClick={() => {
                          if (active) voice.stopSpeaking();
                          else void voice.speak(message, true);
                        }}
                      >
                        {preparing ? (
                          <span className="history-replay-spinner" aria-hidden="true" />
                        ) : speaking ? (
                          <StopIcon />
                        ) : (
                          <VolumeIcon />
                        )}
                      </button>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      )}
    </main>
  );
}
