import { useEffect, useId, useRef, useState } from "react";
import type { ReactNode } from "react";
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

function MicIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="9" y="3" width="6" height="12" rx="3" />
      <path d="M5 11v1a7 7 0 0 0 14 0v-1M12 19v3M8 22h8" />
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
      <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.82 2.82-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 .6 1.7 1.7 0 0 0-.4 1.1V21H9.6v-.1A1.7 1.7 0 0 0 8 19.4a1.7 1.7 0 0 0-1.88.34l-.06.06-2.82-2.82.06-.06A1.7 1.7 0 0 0 3.6 15a1.7 1.7 0 0 0-.6-1 1.7 1.7 0 0 0-1.1-.4H2V9.6h-.1A1.7 1.7 0 0 0 3.6 8a1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.82-2.82.06.06A1.7 1.7 0 0 0 8 3.6a1.7 1.7 0 0 0 1-.6 1.7 1.7 0 0 0 .4-1.1V2h4v-.1A1.7 1.7 0 0 0 15 3.6a1.7 1.7 0 0 0 1.88-.34l.06-.06 2.82 2.82-.06.06A1.7 1.7 0 0 0 19.4 8a1.7 1.7 0 0 0 .6 1 1.7 1.7 0 0 0 1.1.4h.1v4h-.1a1.7 1.7 0 0 0-1.7 1.6Z" />
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
      <path d="M12 5v14M5 12h14" />
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

function Overlay({
  title,
  description,
  onClose,
  children,
}: {
  title: string;
  description?: string;
  onClose?: () => void;
  children: ReactNode;
}) {
  const titleId = useId();
  return (
    <div className="overlay" role="presentation">
      <section
        className="overlay-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <div className="overlay-heading">
          <h2 id={titleId}>{title}</h2>
          {onClose && (
            <button className="plain-icon" onClick={onClose} aria-label="닫기">
              <CloseIcon />
            </button>
          )}
        </div>
        {description && <p className="overlay-description">{description}</p>}
        {children}
      </section>
    </div>
  );
}

export default function App() {
  const voice = useVoiceConversation();
  const selection = useRef(0);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const [shapeIndex, setShapeIndex] = useState(0);
  const [composerOpen, setComposerOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
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
    if (voice.transcript) {
      setComposerOpen(true);
      window.setTimeout(() => textarea.current?.focus(), 0);
    }
  }, [voice.transcript]);

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
        : "마이크로 이야기하기";

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
          className="plain-icon"
          aria-label="새 이야기"
          disabled={voice.busy}
          onClick={() => void voice.newConversation()}
        >
          <PlusIcon />
        </button>
        <button
          className="plain-icon"
          aria-label="대화 설정"
          onClick={() => voice.setSettingsOpen(true)}
        >
          <SettingsIcon />
        </button>
      </nav>

      <Orb signal={voice.signal} selection={selection} />

      <section className="answer-stage" aria-live="polite">
        {voice.latestAnswer ? (
          <>
            {voice.latestUser && (
              <p className="last-question">{voice.latestUser.text}</p>
            )}
            <p className="last-answer">{voice.latestAnswer.text}</p>
          </>
        ) : (
          <p className="orb-prompt">무엇이 궁금해?</p>
        )}
      </section>

      <div className="voice-controls">
        <p className="voice-status" role="status">
          {phaseLabels[voice.phase]}
          {voice.phase === "recording" && (
            <span> {String(voice.seconds).padStart(2, "0")} / 60초</span>
          )}
        </p>
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
            aria-label={microphoneLabel}
            aria-pressed={voice.phase === "recording"}
            onClick={toggleMicrophone}
            disabled={
              voice.busy && !["recording", "acquiring"].includes(voice.phase)
            }
          >
            {["recording", "acquiring"].includes(voice.phase) ? (
              <StopIcon />
            ) : (
              <MicIcon />
            )}
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
            void voice.send(event).then(() => setComposerOpen(false));
          }}
        >
          <div className="composer-copy">
            <label htmlFor="message">
              {voice.transcript
                ? "이렇게 들었어요. 맞는지 확인해 주세요."
                : "글로 이야기하기"}
            </label>
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
          </div>
          <div className="composer-row">
            <textarea
              ref={textarea}
              id="message"
              value={voice.draft}
              onChange={(event) => voice.setDraft(event.target.value)}
              placeholder="궁금한 것을 말하거나 적어 주세요"
              maxLength={1000}
              rows={2}
              disabled={voice.busy}
              onKeyDown={(event) => {
                if (
                  event.key === "Enter" &&
                  !event.shiftKey &&
                  !event.nativeEvent.isComposing
                ) {
                  event.preventDefault();
                  void voice.send().then(() => setComposerOpen(false));
                }
              }}
            />
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

      {voice.error && (
        <div className="error-toast" role="alert">
          <span>{voice.error}</span>
          <button
            className="plain-icon"
            aria-label="안내 닫기"
            onClick={() => voice.setError("")}
          >
            <CloseIcon />
          </button>
        </div>
      )}

      <p className="powered">
        {providerLabel(voice.latestAnswer?.provider)}
      </p>

      {voice.consentOpen && (
        <Overlay
          title="목소리로 이야기해 볼까요?"
          description="녹음한 음성은 글로 바꾸기 위해 OpenAI에 전송돼요. 이리 서버에는 녹음 파일을 저장하지 않아요."
          onClose={() => voice.setConsentOpen(false)}
        >
          <div className="overlay-actions">
            <button
              className="quiet-button"
              onClick={() => {
                voice.setConsentOpen(false);
                setComposerOpen(true);
              }}
            >
              글로 이야기하기
            </button>
            <button className="solid-button" onClick={voice.acceptConsent}>
              동의하고 말하기
            </button>
          </div>
        </Overlay>
      )}

      {voice.settingsOpen && (
        <Overlay
          title="대화 설정"
          description="아이의 나이에 맞춰 쉽게 설명해요."
          onClose={() => voice.setSettingsOpen(false)}
        >
          <fieldset className="setting-group">
            <legend>아이 나이</legend>
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
            <span>
              답변을 목소리로 듣기
              <small>꺼 두어도 모든 답변을 글로 볼 수 있어요.</small>
            </span>
            <input
              type="checkbox"
              checked={voice.autoRead}
              onChange={(event) => voice.setAutoRead(event.target.checked)}
            />
          </label>
        </Overlay>
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
              onClick={() => setHistoryOpen(false)}
            >
              <CloseIcon />
            </button>
          </div>
          <div className="history-list" role="log">
            {voice.messages.map((message) => (
              <article key={message.id} data-role={message.role}>
                <span>{message.role === "user" ? "나" : "이리"}</span>
                <p>{message.text}</p>
              </article>
            ))}
          </div>
        </div>
      )}
    </main>
  );
}
