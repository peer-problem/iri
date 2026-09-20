import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { AudioSignal } from "./audio-level";
import { amplitude, microphoneMotion, rmsLevel } from "./audio-level";
import { ApiError, jsonRequest, request } from "./api";
import { PcmStreamPlayer } from "./pcm";
import { parseProvider } from "./provider";
import type { Provider } from "./provider";
import { consumeVerifiedSpeech, sha256Hex } from "./speech-stream";

export type Phase =
  | "idle"
  | "acquiring"
  | "recording"
  | "transcribing"
  | "thinking"
  | "synthesizing"
  | "speaking";

export type Message = {
  id: string;
  role: "user" | "assistant";
  text: string;
  provider?: Provider;
};

type AudioClip =
  | { format: "pcm"; bytes: ArrayBuffer }
  | { format: "wav"; bytes: ArrayBuffer; url: string };

export const phaseLabels: Record<Phase, string> = {
  idle: "이야기할 준비가 됐어요",
  acquiring: "마이크 사용 권한을 기다리고 있어요",
  recording: "듣고 있어요",
  transcribing: "이야기를 글로 옮기고 있어요",
  thinking: "함께 생각하고 있어요",
  synthesizing: "목소리를 준비하고 있어요",
  speaking: "이리가 이야기하고 있어요",
};

export function useVoiceConversation() {
  const [age, setAge] = useState("4-6");
  const [autoRead, setAutoRead] = useState(true);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [phase, setPhase] = useState<Phase>("idle");
  const [playbackMessageId, setPlaybackMessageId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [transcript, setTranscript] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [error, setError] = useState("");
  const [seconds, setSeconds] = useState(0);

  const recorder = useRef<MediaRecorder | null>(null);
  const recordingAttempt = useRef(0);
  const stream = useRef<MediaStream | null>(null);
  const mediaAudio = useRef<HTMLAudioElement | null>(null);
  const playbackContext = useRef<AudioContext | null>(null);
  const playbackSource = useRef<AudioBufferSourceNode | null>(null);
  const playbackAnalyser = useRef<AnalyserNode | null>(null);
  const playbackSamples = useRef<Float32Array<ArrayBuffer> | null>(null);
  const pcmPlayer = useRef<PcmStreamPlayer | null>(null);
  const playbackAbort = useRef<AbortController | null>(null);
  const playbackAttempt = useRef(0);
  const audioClips = useRef(new Map<string, AudioClip>());
  const inputContext = useRef<AudioContext | null>(null);
  const inputAnalyser = useRef<AnalyserNode | null>(null);
  const inputSamples = useRef<Float32Array<ArrayBuffer> | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const controller = useRef<AbortController | null>(null);
  const phaseRef = useRef<Phase>("idle");
  const syntheticSpeechStarted = useRef(0);

  const signal = useRef<AudioSignal>({
    state: "idle",
    read: () => 0,
    readInput: () => 0,
  });

  const readInput = () => {
    const analyser = inputAnalyser.current;
    const samples = inputSamples.current;
    if (!analyser || !samples || analyser.context.state !== "running") return 0;
    analyser.getFloatTimeDomainData(samples);
    return rmsLevel(samples);
  };
  const readPlayback = () => {
    const analyser = playbackAnalyser.current;
    const samples = playbackSamples.current;
    if (analyser && samples && analyser.context.state === "running") {
      analyser.getFloatTimeDomainData(samples);
      return amplitude(samples, 5.2);
    }
    if (phaseRef.current === "speaking") {
      const elapsed = (performance.now() - syntheticSpeechStarted.current) / 1000;
      return 0.08 + 0.045 * (0.5 + 0.5 * Math.sin(elapsed * 7.2));
    }
    return 0;
  };
  signal.current.readInput = readInput;
  signal.current.read = () =>
    signal.current.state === "listening"
      ? microphoneMotion(readInput())
      : signal.current.state === "talking"
        ? readPlayback()
        : 0;

  const busy = phase !== "idle" && phase !== "speaking";
  const latestUser = [...messages].reverse().find((item) => item.role === "user");
  const latestAnswer = [...messages]
    .reverse()
    .find((item) => item.role === "assistant");

  useEffect(() => {
    phaseRef.current = phase;
    signal.current.state =
      phase === "recording"
        ? "listening"
        : phase === "speaking"
          ? "talking"
          : ["transcribing", "thinking", "synthesizing"].includes(phase)
            ? "thinking"
            : "idle";
  }, [phase]);

  useEffect(() => {
    request("/conversation")
      .then(async (response) => {
        const saved = await response.json();
        setAge(saved.age_band);
        setMessages(
          saved.messages.map(
            (item: {
              id: string;
              role: "user" | "assistant";
              content: string;
              provider?: unknown;
            }) => ({
              id: item.id,
              role: item.role,
              text: item.content,
              provider: parseProvider(item.provider),
            }),
          ),
        );
      })
      .catch(fail);

    return () => {
      cancelRecording();
      stopPlayback();
      controller.current?.abort();
      clearAudio();
      if (playbackContext.current?.state !== "closed") {
        void playbackContext.current?.close();
      }
      playbackContext.current = null;
    };
  }, []);

  function clearAudio() {
    audioClips.current.forEach((clip) => {
      if (clip.format === "wav") URL.revokeObjectURL(clip.url);
    });
    audioClips.current.clear();
  }

  function cacheAudio(id: string, clip: AudioClip) {
    audioClips.current.set(id, clip);
    if (audioClips.current.size <= 12) return;
    const oldest = audioClips.current.keys().next().value;
    if (!oldest) return;
    const previous = audioClips.current.get(oldest);
    if (previous?.format === "wav") URL.revokeObjectURL(previous.url);
    audioClips.current.delete(oldest);
  }

  function releaseMic() {
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
    inputAnalyser.current?.disconnect();
    inputAnalyser.current = null;
    inputSamples.current = null;
    if (inputContext.current?.state !== "closed") {
      void inputContext.current?.close();
    }
    inputContext.current = null;
  }

  function cancelRecording() {
    recordingAttempt.current += 1;
    const active = recorder.current;
    recorder.current = null;
    if (active) {
      active.onstop = null;
      active.onerror = null;
      active.ondataavailable = null;
      if (active.state !== "inactive") active.stop();
    }
    releaseMic();
  }

  function ensurePlaybackAnalyser(context: AudioContext) {
    const current = playbackAnalyser.current;
    if (current && current.context === context) return current;
    current?.disconnect();
    const analyser = context.createAnalyser();
    analyser.fftSize = 1024;
    analyser.smoothingTimeConstant = 0.35;
    analyser.connect(context.destination);
    playbackAnalyser.current = analyser;
    playbackSamples.current = new Float32Array(analyser.fftSize);
    return analyser;
  }

  function stopPlayback() {
    playbackAttempt.current += 1;
    playbackAbort.current?.abort();
    playbackAbort.current = null;
    pcmPlayer.current?.stop();
    pcmPlayer.current = null;
    if (playbackSource.current) {
      playbackSource.current.onended = null;
      try {
        playbackSource.current.stop();
      } catch {
        /* The source already ended. */
      }
      playbackSource.current.disconnect();
      playbackSource.current = null;
    }
    if (mediaAudio.current) {
      mediaAudio.current.onended = null;
      mediaAudio.current.onerror = null;
      mediaAudio.current.pause();
    }
    mediaAudio.current = null;
    setPlaybackMessageId(null);
  }

  async function preparePlayback() {
    try {
      const context = playbackContext.current ?? new AudioContext();
      playbackContext.current = context;
      ensurePlaybackAnalyser(context);
      if (context.state === "suspended") await context.resume();
      const silent = context.createBufferSource();
      silent.buffer = context.createBuffer(1, 1, context.sampleRate);
      silent.connect(context.destination);
      silent.onended = () => silent.disconnect();
      silent.start();
    } catch {
      /* A directly clicked replay can still use the media element path. */
    }
  }

  function fail(reason: unknown) {
    setError(
      reason instanceof ApiError
        ? reason.message
        : "연결을 확인한 뒤 다시 시도해 주세요.",
    );
    setPhase("idle");
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
    } catch (reason) {
      fail(reason);
    }
  }

  async function speak(message: Message, userGesture = false) {
    if (userGesture) await preparePlayback();
    stopPlayback();
    const attempt = playbackAttempt.current;
    setPlaybackMessageId(message.id);
    setError("");
    setPhase("synthesizing");
    try {
      let clip = audioClips.current.get(message.id);
      const context = playbackContext.current;
      const destination = context ? ensurePlaybackAnalyser(context) : undefined;

      if (!clip && context?.state === "running" && destination) {
        const abort = new AbortController();
        playbackAbort.current = abort;
        const response = await jsonRequest(
          "/speech-stream",
          { text: message.text },
          AbortSignal.any([abort.signal, AbortSignal.timeout(65_000)]),
        );
        const player = new PcmStreamPlayer(
          context,
          () => {
            if (playbackAttempt.current === attempt) {
              pcmPlayer.current = null;
              setPlaybackMessageId(null);
              setPhase("idle");
            }
          },
          destination,
        );
        pcmPlayer.current = player;
        const completion = await consumeVerifiedSpeech(response, (value) => {
          if (playbackAttempt.current !== attempt) {
            throw new DOMException("Playback stopped", "AbortError");
          }
          player.push(value);
          if (player.hasStarted) {
            syntheticSpeechStarted.current = performance.now();
            setPhase("speaking");
          }
        });
        if (playbackAttempt.current !== attempt) return;
        const bytes = player.finish();
        if (
          bytes.byteLength !== completion.bytes ||
          (await sha256Hex(bytes)) !== completion.sha256
        ) {
          throw new Error("Incomplete audio");
        }
        cacheAudio(message.id, { format: "pcm", bytes });
        playbackAbort.current = null;
        return;
      }

      if (!clip || (clip.format === "pcm" && context?.state !== "running")) {
        const response = await jsonRequest("/speech", { text: message.text });
        if (playbackAttempt.current !== attempt) return;
        const bytes = await response.arrayBuffer();
        if (playbackAttempt.current !== attempt) return;
        clip = {
          format: "wav",
          bytes,
          url: URL.createObjectURL(new Blob([bytes], { type: "audio/wav" })),
        };
        cacheAudio(message.id, clip);
      }

      if (playbackAttempt.current !== attempt) return;
      if (clip.format === "pcm" && context?.state === "running" && destination) {
        const player = new PcmStreamPlayer(
          context,
          () => {
            if (playbackAttempt.current === attempt) {
              pcmPlayer.current = null;
              setPlaybackMessageId(null);
              setPhase("idle");
            }
          },
          destination,
        );
        pcmPlayer.current = player;
        player.push(new Uint8Array(clip.bytes));
        syntheticSpeechStarted.current = performance.now();
        setPhase("speaking");
        player.finish();
        return;
      }

      if (clip.format !== "wav") throw new Error("Audio playback is unavailable");
      if (context?.state === "running" && destination) {
        try {
          const buffer = await context.decodeAudioData(clip.bytes.slice(0));
          const source = context.createBufferSource();
          source.buffer = buffer;
          source.connect(destination);
          playbackSource.current = source;
          source.onended = () => {
            if (playbackSource.current === source) {
              playbackSource.current = null;
              source.disconnect();
              setPlaybackMessageId(null);
              setPhase("idle");
            }
          };
          source.start();
          syntheticSpeechStarted.current = performance.now();
          setPhase("speaking");
          return;
        } catch {
          /* Fall back to the media element path. */
        }
      }

      const player = new Audio(clip.url);
      mediaAudio.current = player;
      player.onended = () => {
        if (playbackAttempt.current !== attempt || mediaAudio.current !== player) return;
        mediaAudio.current = null;
        setPlaybackMessageId(null);
        setPhase("idle");
      };
      player.onerror = () => {
        if (playbackAttempt.current !== attempt || mediaAudio.current !== player) return;
        mediaAudio.current = null;
        setPlaybackMessageId(null);
        setPhase("idle");
        setError("음성을 재생하지 못했어요. 다시 듣기를 눌러 주세요.");
      };
      try {
        await player.play();
        syntheticSpeechStarted.current = performance.now();
        setPhase("speaking");
      } catch {
        if (playbackAttempt.current !== attempt) return;
        mediaAudio.current = null;
        setPlaybackMessageId(null);
        setPhase("idle");
        setError("다시 듣기를 누르면 이리의 목소리를 들을 수 있어요.");
      }
    } catch (reason) {
      if (playbackAttempt.current !== attempt) return;
      pcmPlayer.current?.stop();
      pcmPlayer.current = null;
      setPlaybackMessageId(null);
      fail(reason);
      if (!(reason instanceof ApiError && reason.status === 401)) {
        setError(
          "답변은 준비됐지만 음성 연결이 어려워요. 잠시 후 다시 듣기를 눌러 주세요.",
        );
      }
    }
  }

  async function send(event?: FormEvent) {
    event?.preventDefault();
    if (!draft.trim() || busy) return;
    const question = draft.trim();
    if (autoRead) await preparePlayback();
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
        provider: parseProvider(result.provider),
      };
      setMessages((current) =>
        [
          ...current,
          { id: crypto.randomUUID(), role: "user" as const, text: question },
          answer,
        ].slice(-12),
      );
      setDraft("");
      setTranscript(false);
      setPhase("idle");
      if (autoRead) await speak(answer);
    } catch (reason) {
      fail(reason);
    }
  }

  async function startRecording() {
    if (busy) return;
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
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: false,
        },
      });
      if (attempt !== recordingAttempt.current) {
        media.getTracks().forEach((track) => track.stop());
        return;
      }
      stream.current = media;
      const mime = ["audio/webm;codecs=opus", "audio/mp4", "audio/webm"].find(
        (type) => MediaRecorder.isTypeSupported(type),
      );
      if (!mime) throw new Error("unsupported");

      const activeRecorder = new MediaRecorder(media, {
        mimeType: mime,
        audioBitsPerSecond: 64_000,
      });
      recorder.current = activeRecorder;
      const chunks: Blob[] = [];
      activeRecorder.ondataavailable = (event) => {
        if (event.data.size) chunks.push(event.data);
      };
      activeRecorder.onerror = () => {
        cancelRecording();
        setPhase("idle");
        setError("녹음하지 못했어요. 마이크 연결을 확인해 주세요.");
      };
      activeRecorder.onstop = async () => {
        releaseMic();
        recorder.current = null;
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
            headers: {
              "Content-Type": blob.type,
              "X-Audio-Consent": "true",
            },
            body: blob,
          });
          const result = await response.json();
          setDraft(result.text);
          setTranscript(true);
          setPhase("idle");
        } catch (reason) {
          fail(reason);
        }
      };
      activeRecorder.start(250);
      setPhase("recording");

      let elapsed = 0;
      timer.current = setInterval(() => {
        elapsed += 1;
        setSeconds(elapsed);
        if (elapsed >= 60 && activeRecorder.state === "recording") {
          activeRecorder.stop();
        }
      }, 1000);

      try {
        const context = new AudioContext();
        inputContext.current = context;
        await context.resume();
        const analyser = context.createAnalyser();
        analyser.fftSize = 1024;
        context.createMediaStreamSource(media).connect(analyser);
        inputAnalyser.current = analyser;
        inputSamples.current = new Float32Array(analyser.fftSize);
      } catch {
        /* Recording remains available without visual metering. */
      }
    } catch (reason) {
      if (attempt !== recordingAttempt.current) return;
      cancelRecording();
      setPhase("idle");
      setError(
        reason instanceof DOMException && reason.name === "NotAllowedError"
          ? "마이크 권한이 꺼져 있어요. 주소창에서 허용하거나 글로 입력해 주세요."
          : "마이크를 연결하지 못했어요. 글로도 이야기할 수 있어요.",
      );
    }
  }

  function finishRecording() {
    if (recorder.current?.state === "recording") recorder.current.stop();
  }

  function cancelMicRequest() {
    cancelRecording();
    setPhase("idle");
  }

  function stopSpeaking() {
    stopPlayback();
    setPhase("idle");
  }

  return {
    age,
    autoRead,
    setAutoRead,
    settingsOpen,
    setSettingsOpen,
    phase,
    playbackMessageId,
    draft,
    setDraft,
    transcript,
    setTranscript,
    messages,
    latestUser,
    latestAnswer,
    error,
    setError,
    seconds,
    signal,
    busy,
    newConversation,
    speak,
    send,
    startRecording,
    finishRecording,
    cancelMicRequest,
    stopSpeaking,
  };
}
