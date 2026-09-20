import { Fragment, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { ResearchIllustration } from "./ResearchIllustration";

const HF = "https://huggingface.co/peerproblem/Kanana-IRI-3B-QLoRA";
const GITHUB = "https://github.com/peer-problem/iri";
const steps = [
  ["입력 및 전사", "음성을 글로 변환하고 사용자가 확인합니다. 텍스트 입력도 지원합니다.", "gpt-4o-mini-transcribe"],
  ["입력 분류", "질문을 검사해 답변 생성 또는 안내와 확인 질문을 선택합니다.", "Base model + policy"],
  ["답변 생성", "연령 설정과 최근 대화 문맥을 반영해 한국어 답변을 생성합니다.", "Kanana 2 3B + IRI v5"],
  ["출력 검사", "생성된 답변을 다시 검사하고 전달 여부를 결정합니다.", "Base model + policy"],
  ["음성 합성", "검사를 통과한 답변을 음성으로 변환합니다.", "gpt-4o-mini-tts-2025-12-15"],
];
const experiments = [
  ["v1", "50", "12", "해당 없음", "초기 실험. 일반 질문 평가에서 기본 모델 대비 저하"],
  ["v2", "268", "62", "2.247578", "어댑터 재로딩 확인. 전체 행동 평가 미완료"],
  ["v3", "332", "76", "2.145101", "평가 300건 중 행동 기준 충족 239건. 채택 제외"],
  ["v4", "372", "84", "2.146981", "독립 평가 60건 중 행동 기준 충족 46건. 채택 제외"],
  ["v5", "412", "92", "2.103572", "현재 선택 버전. 독립 최종 평가 미완료"],
];
const features = [
  ["음성 및 텍스트 입력", "최대 60초 녹음. 전사문을 수정하고 확인한 뒤 전송", "마이크 / 키보드"],
  ["연령별 응답 설정", "4~6세 또는 7~10세. 연령 변경 시 대화 문맥 초기화", "연령 선택"],
  ["대화 기록과 재생", "이전 답변 확인과 다시 듣기. 재생 중지 지원", "기록 / 재생 / 중지"],
  ["대화 데이터 보관", "최근 6턴을 서버 메모리에 최대 1시간 보관. 디스크 비저장", "새 이야기로 초기화"],
];

function ExternalLink({ href, children }: { href: string; children: ReactNode }) {
  const brand = href.startsWith("https://huggingface.co/") ? "hugging-face" : href.startsWith("https://github.com/") ? "github" : null;
  return <a className={brand ? "brand-link" : undefined} href={href} target="_blank" rel="noreferrer">{brand && <img className="brand-icon" src={`/brands/${brand}.svg`} width="17" height="17" alt="" aria-hidden="true" />}{children}<span className="sr-only"> (새 탭)</span></a>;
}

export default function LandingPage() {
  const [paused, setPaused] = useState(false);
  useEffect(() => {
    document.title = "IRI | 아동을 위한 한국어 음성 대화 AI";
    document.body.classList.add("landing-body");
    return () => document.body.classList.remove("landing-body");
  }, []);

  return (
    <div className="research-page" data-paused={paused}>
      <a className="research-skip" href="#product">본문으로 이동</a>
      <header className="paper-nav">
        <a className="product-wordmark" href="/" aria-label="IRI 홈">iri<span className="brand-dot" /></a>
        <nav aria-label="페이지 메뉴"><ExternalLink href={GITHUB}>GitHub</ExternalLink><ExternalLink href={HF}>Hugging Face</ExternalLink><a className="nav-demo" href="/chat" target="_blank" rel="noopener noreferrer">대화 시작 ↗<span className="sr-only"> (새 탭)</span></a></nav>
      </header>
      <main className="paper">
        <header className="product-intro" id="product">
          <div><h1>IRI: 아동을 위한 한국어 음성 대화 AI</h1></div>
          <div className="product-description">
            <p>IRI는 아이의 나이에 맞는 어휘와 설명 길이를 목표로 만든 대화 AI입니다. 말이나 글로 질문하고, 확인한 답변을 음성으로 들을 수 있습니다.</p>
            <a className="demo-preview" href="/chat" target="_blank" rel="noopener noreferrer" aria-label="데모 보기 (새 탭)">
              <span className="demo-window">
                <span className="demo-window-bar" aria-hidden="true"><span className="demo-window-dots"><i /><i /><i /></span><span>iri.today/chat</span><span className="demo-window-open">↗</span></span>
                <img src="/previews/chat.webp" width="960" height="600" alt="IRI 대화 화면 미리보기" fetchPriority="high" />
              </span>
              <span className="demo-preview-label">데모 보기 <span aria-hidden="true">↗</span></span>
            </a>
          </div>
        </header>
        <div className="paper-columns product-overview">
          <div><p className="overview-link"><ExternalLink href={HF}>Hugging Face</ExternalLink></p><p>Kanana 2 3B Instruct에 연령별 대화 예시로 QLoRA 어댑터를 학습했습니다. 학습한 다섯 버전의 어댑터는 Hugging Face에 공개했습니다.</p></div>
          <div><p className="overview-link"><ExternalLink href={GITHUB}>GitHub</ExternalLink></p><p>대화 하네스는 입력 검사와 답변 생성 및 출력 검사를 수행하고 음성 인터페이스와 연결됩니다. 구현 코드와 평가 기록은 GitHub에서 확인할 수 있습니다.</p></div>
        </div>
        <ResearchIllustration kind="conversation" paused={paused} caption="음성 또는 텍스트 입력 → 전사문 확인 → 검사와 답변 생성 → 음성 재생" />
        <section id="training" className="paper-section" aria-labelledby="training-title">
          <div className="section-heading"><h2 id="training-title">QLoRA 파인튜닝</h2><p>Kanana 2 3B Instruct에 QLoRA 어댑터를 학습했습니다. 기본 모델에 연령별 대화 예시를 더해, 4~6세와 7~10세에 맞춘 어휘와 설명 길이를 조정하는 방식입니다.</p></div>
          <ResearchIllustration kind="adapter" paused={paused} caption="QLoRA 개념도. 기본 가중치는 고정하고 LoRA의 작은 행렬 A와 B를 학습합니다. 행렬 크기와 입자는 설명을 위한 표현입니다." />
          <div className="paper-columns training-notes"><section><h3>기본 모델 + 작은 추가 학습</h3><p>원본 모델과 어댑터를 구분했습니다. 답변 생성에는 IRI v5 어댑터를 적용하고, 질문과 답변 검사에는 기본 모델과 제품 정책을 사용합니다. <ExternalLink href="https://arxiv.org/abs/2305.14314">QLoRA 방식 ↗</ExternalLink></p></section><section><h3>실패 사례를 보강하며 v5까지</h3><p>이전 평가에서 발견한 실패 유형을 다음 학습 데이터에 반영했습니다. 학습한 어댑터는 새 프로세스에서 다시 불러 생성 동작도 확인했습니다.</p></section></div>
        </section>
        <section id="evaluation" className="paper-section" aria-labelledby="evaluation-title">
          <div className="table-heading"><h3 id="evaluation-title">다섯 버전의 학습 기록</h3><ExternalLink href={`${GITHUB}/blob/main/runpod/artifacts/kanana-performance-assessment-20260919/README.md`}>평가 기록 ↗</ExternalLink></div>
          <table className="paper-table results-table"><caption className="sr-only">버전별 학습 데이터와 평가 결과</caption><thead><tr><th scope="col">버전</th><th scope="col">학습 수</th><th scope="col">검증 수</th><th scope="col">검증 손실</th><th scope="col" className="result-wide">결과 및 상태</th></tr></thead><tbody>{experiments.map(([version, train, valid, loss, result]) => <Fragment key={version}><tr className={version === "v5" ? "selected" : undefined}><th scope="row" id={`experiment-${version}`}>{version}</th><td>{train}</td><td>{valid}</td><td>{loss}</td><td className="result-wide">{result}</td></tr><tr className={`result-narrow ${version === "v5" ? "selected" : ""}`}><td colSpan={4} headers={`experiment-${version}`}>{result}</td></tr></Fragment>)}</tbody></table>
          <p className="paper-note">v2~v5는 3 epochs로 학습했습니다. 검증 데이터 구성이 달라 손실값만으로 응답 품질을 비교할 수 없습니다. 행동 평가는 AI가 작성한 기준에 따른 판정이며 사람 대상 실험이 아닙니다.</p>
          <p className="validation-note"><strong>확인한 것과 남은 것.</strong> v5는 새 프로세스에서 대표 답변 5건의 생성을 확인했습니다. 다만 독립 최종 평가와 vLLM 서빙 검증은 아직 끝나지 않았으며, 위 수치는 아동 대상 사용 적합성을 인증하지 않습니다.</p>
        </section>
        <section id="system" className="paper-section" aria-labelledby="system-title">
          <div className="section-heading"><h2 id="system-title">대화 처리 구조</h2><p>학습한 모델 앞뒤에 검사 단계를 두고 음성 인터페이스를 연결했습니다. 이 실행 구조가 대화 하네스입니다. 질문을 분류한 뒤 답변을 만들고, 생성된 답변을 다시 검사해 전달 여부를 정합니다.</p></div>
          <ResearchIllustration kind="inspection" paused={paused} caption="일반 답변 경로와 안내 응답 분기. 대체 모델도 입력 검사부터 전체 경로를 다시 수행합니다." />
          <table className="paper-table pipeline-table"><caption>대화 하네스의 다섯 단계</caption><thead><tr><th scope="col">단계</th><th scope="col">처리 내용</th><th scope="col">구성 요소</th></tr></thead><tbody>{steps.map(([stage, detail, runtime], i) => <tr key={stage}><th scope="row"><span className="step-index">{i + 1}.</span> {stage}</th><td>{detail}</td><td><code>{runtime}</code></td></tr>)}</tbody></table>
          <div className="paper-columns findings"><section><h3>연결이 끊겼을 때의 대체 경로</h3><p>Kanana를 사용할 수 없으면 대체 모델이 입력 검사부터 전체 경로를 다시 수행합니다. 이때도 같은 연령 설정과 응답 정책을 적용합니다.</p></section><section><h3>검사를 통과한 답변만 음성으로</h3><p>출력 검사 이후 음성을 합성합니다. 다만 검사는 위험한 응답을 줄이기 위한 장치이며, 모든 오류를 차단하거나 답변의 안전성을 보장하지는 않습니다.</p></section></div>
        </section>
        <section id="implementation" className="paper-section" aria-labelledby="implementation-title">
          <div className="section-heading"><h2 id="implementation-title">대화 기능과 데이터 보관</h2><p>음성으로 질문해도 전사문을 먼저 확인합니다. 연령을 바꾸거나 새 이야기를 시작하면 대화 문맥을 초기화하고, 이전 답변은 기록에서 다시 들을 수 있습니다.</p></div>
          <table className="paper-table features-table"><caption className="sr-only">사용자가 확인하고 제어할 수 있는 기능</caption><thead><tr><th scope="col">기능</th><th scope="col">지원 범위</th><th scope="col">사용자 제어</th></tr></thead><tbody>{features.map(([feature, scope, control]) => <tr key={feature}><th scope="row">{feature}</th><td>{scope}</td><td>{control}</td></tr>)}</tbody></table>
          <p className="paper-note">음성 인식과 합성 및 대체 응답에는 외부 API를 사용하며, 처리 과정에서 입력 데이터가 외부 제공자에게 전달됩니다. 민감한 개인정보는 입력하지 마세요.</p>
        </section>

        <div className="paper-figure-pair">
          <ResearchIllustration kind="age" paused={paused} caption="4~6세 / 7~10세에 맞춘 어휘와 설명 길이 설정" />
          <ResearchIllustration kind="memory" paused={paused} caption="최근 6턴만 서버 메모리에 보관. 최대 1시간 후 만료" />
        </div>

        <section id="resources" className="paper-section paper-resources" aria-labelledby="resources-title"><h2 id="resources-title">모델과 소스 코드</h2><p>Hugging Face에서 IRI v5 어댑터와 이전 버전을 확인할 수 있습니다. 대화 하네스와 평가 기록은 GitHub에 공개했습니다. 기본 모델 가중치와 서비스 검사 로직은 어댑터에 포함되지 않습니다.</p><ul className="resource-links"><li><ExternalLink href={HF}>Hugging Face</ExternalLink>: QLoRA 어댑터 v1~v5</li><li><ExternalLink href={GITHUB}>GitHub</ExternalLink>: 구현 코드와 평가 기록</li><li><a href="/chat">IRI 데모</a>: 음성과 텍스트 대화</li></ul></section>
        <footer className="paper-footer"><span>iri / Kanana 기반 한국어 음성 대화 AI</span><button type="button" aria-pressed={paused} onClick={() => setPaused(!paused)}>{paused ? "삽화 움직임 재개" : "삽화 움직임 멈추기"}</button></footer>
      </main>
    </div>
  );
}
