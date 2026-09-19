import { useEffect, useRef } from "react";
import type { AudioSignal } from "./audio-level";
import { Orb } from "./Orb";

const processSteps = [
  {
    number: "01",
    title: "말하고 적어요",
    body: "아이의 질문을 마이크나 글로 받습니다.",
  },
  {
    number: "02",
    title: "먼저 확인해요",
    body: "음성을 글로 바꾼 뒤, 아이가 들은 문장을 직접 확인합니다.",
  },
  {
    number: "03",
    title: "질문의 맥락을 살펴요",
    body: "생성 전에 입력을 검사해 답하기, 안내하기, 되묻기를 구분합니다.",
  },
  {
    number: "04",
    title: "Kanana가 답해요",
    body: "Kanana 2 3B Instruct에 IRI v5 QLoRA를 더해 나이에 맞는 한국어 답을 만듭니다.",
  },
  {
    number: "05",
    title: "답을 한 번 더 살펴요",
    body: "아이에게 전달하기 전에 출력 검사와 제품 정책을 다시 통과합니다.",
  },
  {
    number: "06",
    title: "목소리로 들려줘요",
    body: "승인된 답만 따뜻한 음성과 반응하는 오브로 전달합니다.",
  },
];

const featureItems = [
  {
    number: "01",
    title: "목소리와 글, 둘 다",
    body: "말하기가 편한 순간에는 마이크로, 조용히 묻고 싶은 순간에는 키보드로 대화합니다.",
  },
  {
    number: "02",
    title: "두 개의 눈높이",
    body: "4~6세에게는 더 짧고 익숙하게, 7~10세에게는 쉬운 원인까지 덧붙여 설명합니다.",
  },
  {
    number: "03",
    title: "대화는 잠시만",
    body: "최근 여섯 턴만 서버 메모리에 최대 한 시간 보관합니다. 녹음과 대화는 디스크에 저장하지 않습니다.",
  },
  {
    number: "04",
    title: "상태가 보이는 오브",
    body: "듣기, 생각하기, 말하기의 리듬을 색과 움직임으로 보여주어 대화의 흐름을 놓치지 않게 합니다.",
  },
];

function ArrowIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 12h13M13 6l6 6-6 6" />
    </svg>
  );
}

function ExternalIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M8 16 16 8M9 8h7v7" />
      <path d="M16 14v5H5V8h5" />
    </svg>
  );
}

export default function LandingPage() {
  const page = useRef<HTMLElement>(null);
  const selection = useRef(0);
  const signal = useRef<AudioSignal>({
    state: "thinking",
    read: () => 0.08 + Math.max(0, Math.sin(performance.now() / 720)) * 0.08,
    readInput: () => 0,
  });

  useEffect(() => {
    document.title = "IRI | 질문이 자라는 대화";
    document.body.classList.add("landing-body");

    const root = page.current;
    if (!root) return;

    let frame = 0;
    const updateScroll = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const available = Math.max(
          1,
          document.documentElement.scrollHeight - window.innerHeight,
        );
        root.style.setProperty(
          "--landing-progress",
          String(Math.min(1, window.scrollY / available)),
        );
        root.dataset.scrolled = window.scrollY > 28 ? "true" : "false";
      });
    };

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) entry.target.classList.add("is-visible");
        }
      },
      { threshold: 0.16 },
    );

    root.querySelectorAll(".reveal").forEach((node) => observer.observe(node));
    window.addEventListener("scroll", updateScroll, { passive: true });
    updateScroll();

    const states: AudioSignal["state"][] = [
      "thinking",
      "talking",
      "idle",
      "listening",
    ];
    let stateIndex = 0;
    const stateTimer = window.setInterval(() => {
      stateIndex = (stateIndex + 1) % states.length;
      signal.current.state = states[stateIndex];
    }, 2800);

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener("scroll", updateScroll);
      window.clearInterval(stateTimer);
      document.body.classList.remove("landing-body");
    };
  }, []);

  return (
    <main className="landing-page" ref={page}>
      <header className="landing-header">
        <a className="landing-brand" href="#top" aria-label="IRI 처음으로">
          iri
          <span aria-hidden="true">✳</span>
        </a>
        <nav className="landing-nav" aria-label="주요 메뉴">
          <a href="#story">프로젝트</a>
          <a href="#model">모델</a>
          <a href="#features">기능</a>
          <a className="nav-demo" href="/chat">
            대화 시작
            <ArrowIcon />
          </a>
        </nav>
      </header>

      <section className="landing-hero" id="top">
        <div className="hero-copy">
          <p className="hero-kicker">Korean voice companion / ages 4 to 10</p>
          <h1>
            질문이
            <br />
            자라는 대화.
          </h1>
          <p className="hero-description">
            Kanana 3B를 아이의 눈높이에 맞게 직접 학습하고,
            <br className="desktop-break" /> 말하고 듣는 하나의 경험으로 만들었습니다.
          </p>
          <div className="hero-actions">
            <a className="primary-link" href="/chat">
              이리와 대화하기
              <ArrowIcon />
            </a>
            <a
              className="text-link"
              href="https://huggingface.co/peerproblem/Kanana-IRI-3B-QLoRA"
              target="_blank"
              rel="noreferrer"
            >
              Hugging Face
              <ExternalIcon />
            </a>
          </div>
          <p className="hero-model-note">
            Kanana 2 3B Instruct <span>+</span> IRI v5 QLoRA
          </p>
        </div>

        <div className="hero-orb" aria-hidden="true">
          <div className="hero-orb-halo" />
          <Orb signal={signal} selection={selection} />
          <span className="orb-state orb-state-listen">LISTEN</span>
          <span className="orb-state orb-state-think">THINK</span>
          <span className="orb-state orb-state-speak">SPEAK</span>
        </div>

        <a className="scroll-cue" href="#story">
          <span>SCROLL</span>
          <i aria-hidden="true" />
        </a>
      </section>

      <section className="story-section" id="story">
        <div className="section-index reveal">
          <span>01</span>
          <span>WHY IRI</span>
        </div>
        <div className="story-copy reveal">
          <p className="section-kicker">Curiosity, spoken.</p>
          <h2>
            아이의 질문은 짧아도,
            <br />
            그 안의 호기심은 작지 않으니까.
          </h2>
          <p>
            IRI는 한국어를 쓰는 4~10세 아이를 위한 음성 우선 연구 데모입니다.
            질문을 정확히 듣고, 연령에 맞춰 답하고, 다시 따뜻한 목소리로 들려주는
            과정 전체를 설계했습니다.
          </p>
        </div>
        <div className="story-word" aria-hidden="true">
          iri
        </div>
      </section>

      <section className="process-section">
        <div className="process-heading reveal">
          <div className="section-index light-index">
            <span>02</span>
            <span>HOW IT WORKS</span>
          </div>
          <p className="section-kicker">One question, fully considered.</p>
          <h2>하나의 질문이 답이 되기까지.</h2>
        </div>

        <div className="process-layout">
          <div className="process-orbit" aria-hidden="true">
            <div className="process-core">iri</div>
            <i className="ring ring-one" />
            <i className="ring ring-two" />
            <i className="route-dot dot-one" />
            <i className="route-dot dot-two" />
          </div>
          <ol className="process-list">
            {processSteps.map((step, index) => (
              <li
                className="process-item reveal"
                key={step.number}
                style={{ "--item-delay": `${index * 55}ms` } as React.CSSProperties}
              >
                <span>{step.number}</span>
                <div>
                  <h3>{step.title}</h3>
                  <p>{step.body}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>

        <p className="fallback-note reveal">
          <strong>Kanana가 준비되지 않은 순간에도.</strong>
          GPU가 꺼져 있으면 Luna high가 같은 입력 검사와 생성, 출력 검사 경로를
          처음부터 다시 실행합니다. GPU를 자동으로 켜지 않습니다.
        </p>
      </section>

      <section className="model-section" id="model">
        <div className="section-index reveal">
          <span>03</span>
          <span>THE MODEL</span>
        </div>
        <div className="model-intro reveal">
          <p className="section-kicker">Trained in the open.</p>
          <h2>
            Kanana를 다섯 번,
            <br />더 나은 대화를 향해.
          </h2>
          <p>
            Kakao의 Kanana 2 3B Instruct를 고정한 뒤 QLoRA 어댑터를 v1부터 v5까지
            학습했습니다. 비교 가능한 후보 중 검증 손실이 가장 낮았던 v5를 선택했고,
            모든 버전과 메타데이터를 Hugging Face에 공개했습니다.
          </p>
        </div>

        <div className="release-rail reveal" aria-label="IRI 어댑터 버전 이력">
          {['v1', 'v2', 'v3', 'v4', 'v5'].map((version) => (
            <div key={version} className={version === 'v5' ? 'selected' : ''}>
              <i />
              <span>{version}</span>
              {version === 'v5' && <small>SELECTED</small>}
            </div>
          ))}
        </div>

        <div className="model-facts">
          <div className="model-number reveal">
            <strong>v5</strong>
            <span>selected adapter</span>
          </div>
          <dl className="model-specs reveal">
            <div>
              <dt>Base model</dt>
              <dd>kakaocorp/kanana-2-3b-instruct</dd>
            </div>
            <div>
              <dt>Training method</dt>
              <dd>QLoRA adapter fine-tuning</dd>
            </div>
            <div>
              <dt>Published history</dt>
              <dd>versions/v1 through versions/v5</dd>
            </div>
            <div>
              <dt>Pinned release</dt>
              <dd>0880ce0372cedf22</dd>
            </div>
          </dl>
        </div>

        <div className="model-actions reveal">
          <a
            className="primary-link"
            href="https://huggingface.co/peerproblem/Kanana-IRI-3B-QLoRA"
            target="_blank"
            rel="noreferrer"
          >
            모델 저장소 보기
            <ExternalIcon />
          </a>
          <a
            className="text-link"
            href="https://github.com/peer-problem/iri"
            target="_blank"
            rel="noreferrer"
          >
            소스 코드
            <ExternalIcon />
          </a>
        </div>

        <p className="research-note reveal">
          <span>RESEARCH NOTE</span>
          IRI는 연구 데모입니다. 선택된 v5의 독립 최종 홀드아웃과 vLLM 서빙 검증은
          아직 완료되지 않았습니다. 아동이 보호자 없이 사용하는 안전 인증 제품으로
          소개하지 않습니다.
        </p>
      </section>

      <section className="features-section" id="features">
        <div className="features-heading reveal">
          <div className="section-index">
            <span>04</span>
            <span>THE EXPERIENCE</span>
          </div>
          <p className="section-kicker">Small details, calmer conversations.</p>
          <h2>아이도, 보호자도 이해할 수 있게.</h2>
        </div>

        <div className="feature-lines">
          {featureItems.map((feature, index) => (
            <article
              className="feature-item reveal"
              key={feature.number}
              style={{ "--item-delay": `${index * 70}ms` } as React.CSSProperties}
            >
              <span>{feature.number}</span>
              <h3>{feature.title}</h3>
              <p>{feature.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="closing-section">
        <div className="closing-glow" aria-hidden="true" />
        <div className="closing-copy reveal">
          <p className="section-kicker">Ready when curiosity is.</p>
          <h2>무엇이 궁금해?</h2>
          <p>IRI에게 직접 말해 보세요. 질문은 짧아도 괜찮아요.</p>
          <a className="closing-link" href="/chat">
            대화 시작하기
            <ArrowIcon />
          </a>
        </div>
      </section>

      <footer className="landing-footer">
        <a className="landing-brand footer-brand" href="#top">
          iri<span aria-hidden="true">✳</span>
        </a>
        <p>Curiosity, spoken.</p>
        <div>
          <a
            href="https://huggingface.co/peerproblem/Kanana-IRI-3B-QLoRA"
            target="_blank"
            rel="noreferrer"
          >
            Hugging Face
          </a>
          <a
            href="https://github.com/peer-problem/iri"
            target="_blank"
            rel="noreferrer"
          >
            GitHub
          </a>
          <a href="/chat">Demo</a>
        </div>
      </footer>
    </main>
  );
}
