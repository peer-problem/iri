import { Fragment, useEffect } from "react";

const HF = "https://huggingface.co/peerproblem/Kanana-IRI-3B-QLoRA";
const GITHUB = "https://github.com/peer-problem/iri";
const steps = [
  ["입력 및 전사", "음성 또는 텍스트로 질문합니다. 음성은 글로 변환한 뒤 사용자가 확인하고 수정합니다.", "gpt-4o-mini-transcribe"],
  ["입력 분류", "질문을 검사해 답변을 생성할지, 안내하거나 다시 질문할지 결정합니다.", "Base model + product policy"],
  ["답변 생성", "연령 설정과 최근 대화를 반영해 한국어 답변을 생성합니다.", "Kanana 2 3B + IRI v5 QLoRA"],
  ["출력 검사", "생성된 답변을 다시 검사하고 제품 정책에 따라 전달 여부를 결정합니다.", "Base model + product policy"],
  ["음성 합성", "출력 검사를 통과한 답변을 음성으로 변환합니다. 재생 중지와 이전 답변 다시 듣기를 지원합니다.", "gpt-4o-mini-tts-2025-12-15"],
];
const experiments = [
  ["v1", "50", "12", "해당 없음", "초기 실험. 일반 질문 평가에서 기본 모델 대비 저하"],
  ["v2", "268", "62", "2.247578", "어댑터 재로딩 확인. 전체 행동 평가 미완료"],
  ["v3", "332", "76", "2.145101", "평가 300건 중 행동 기준 충족 239건. 채택 제외"],
  ["v4", "372", "84", "2.146981", "독립 평가 60건 중 행동 기준 충족 46건. 채택 제외"],
  ["v5", "412", "92", "2.103572", "현재 선택 버전. 독립 최종 평가 미완료"],
];

function ExternalLink({ href, children }: { href: string; children: React.ReactNode }) {
  return <a href={href} target="_blank" rel="noreferrer">{children}<span aria-hidden="true">↗</span><span className="sr-only"> (새 탭)</span></a>;
}

export default function LandingPage() {
  useEffect(() => {
    document.title = "IRI | Kanana 기반 한국어 음성 대화 연구";
    document.body.classList.add("landing-body");
    return () => document.body.classList.remove("landing-body");
  }, []);

  return (
    <div className="research-page">
      <a className="research-skip" href="#overview">본문으로 이동</a>
      <header className="research-header">
        <a className="research-brand" href="/" aria-label="IRI 홈">iri<span>Research project</span></a>
        <nav aria-label="페이지 메뉴">
          <a href="#system">시스템</a><a href="#evaluation">실험 결과</a><a href="#implementation">구현</a>
          <a className="research-nav-demo" href="/chat">데모 <span aria-hidden="true">↗</span></a>
        </nav>
      </header>

      <main>
        <section className="research-hero" aria-labelledby="research-title">
          <div className="research-hero-inner">
            <div className="research-abstract">
              <p className="research-eyebrow">IRI / Technical overview</p>
              <h1 id="research-title">Kanana 기반 한국어 음성 대화 연구</h1>
              <p className="research-summary">아동의 연령에 맞춘 한국어 응답을 목표로, Kanana 모델의 추가 학습과 음성 대화 인터페이스를 구현한 연구 프로젝트입니다.</p>
              <p className="research-abstract-detail">질문 입력부터 답변 생성, 출력 검사, 음성 재생까지 하나의 대화 흐름으로 연결합니다. 학습 어댑터와 구현 코드를 공개합니다.</p>
              <div className="research-actions"><a className="research-button" href="/chat">데모 실행 <span aria-hidden="true">↗</span></a><ExternalLink href={HF}>Hugging Face</ExternalLink><ExternalLink href={GITHUB}>GitHub</ExternalLink></div>
              <p className="research-status">연구용 데모 <span>/</span> 선택 어댑터 v5 <span>/</span> 독립 최종 평가 미완료</p>
            </div>
          </div>
        </section>

        <div className="research-content">
          <section className="research-section" id="overview" aria-labelledby="overview-title">
            <div className="research-section-label"><span>01</span><h2 id="overview-title">연구 범위</h2><p>Scope & model</p></div>
            <div className="research-section-content">
              <h3>모델과 서비스의 통합 구현</h3>
              <p className="research-lead">어린이는 말이나 글로 질문하고 답변을 듣습니다. 보호자는 연령 설정과 대화 기록을 확인할 수 있습니다. 답변 생성 모델 외에 입력 검사와 출력 검사, 음성 처리를 별도 단계로 구성했습니다.</p>
              <dl className="research-specs">
                <div><dt>기본 모델</dt><dd>Kanana 2 3B Instruct<small>kakaocorp/kanana-2-3b-instruct</small></dd></div>
                <div><dt>학습 방식</dt><dd>QLoRA 어댑터 학습<small>기본 모델에 IRI 추가 학습 결과 적용</small></dd></div>
                <div><dt>응답 연령 설정</dt><dd>4~6세 / 7~10세<small>답변 길이와 어휘 수준 조정</small></dd></div>
                <div><dt>공개 산출물</dt><dd>학습 어댑터 및 구현 코드<small>Hugging Face / GitHub</small></dd></div>
              </dl>
            </div>
          </section>

          <section className="research-section" id="system" aria-labelledby="system-title">
            <div className="research-section-label"><span>02</span><h2 id="system-title">시스템 구성</h2><p>Inference pipeline</p></div>
            <div className="research-section-content">
              <h3>추론 및 음성 처리 절차</h3>
              <p className="research-lead">질문과 답변을 각각 검사합니다. 검사 단계는 위험한 응답을 줄이기 위한 장치이며, 모든 오류를 차단한다는 의미는 아닙니다.</p>
              <ol className="research-pipeline">{steps.map(([title, body, component], i) => <li key={title}><span className="research-step-number">0{i + 1}</span><div><h4>{title}</h4><p>{body}</p></div><code>{component}</code></li>)}</ol>
              <aside className="research-note"><h4>대체 응답 경로</h4><p>Kanana 경로를 사용할 수 없으면 gpt-5.6-luna(high) 경로에서 입력 검사부터 다시 수행합니다. 실제 응답에 사용된 경로는 대화 화면에 표시합니다.</p></aside>
            </div>
          </section>

          <section className="research-section" id="evaluation" aria-labelledby="evaluation-title">
            <div className="research-section-label"><span>03</span><h2 id="evaluation-title">학습 및 평가</h2><p>Experiments & limitations</p></div>
            <div className="research-section-content">
              <h3>학습 버전별 기록</h3>
              <p className="research-lead">데이터를 보강하며 다섯 차례 어댑터를 학습했습니다. 아래 수치는 학습 기록이며, 제품의 안전성이나 아동 대상 사용 적합성을 인증하는 지표가 아닙니다.</p>
              <table className="research-table"><caption>TABLE 01. 학습 데이터 및 평가 기록</caption><thead><tr><th scope="col">버전</th><th scope="col">학습 수</th><th scope="col">검증 수</th><th scope="col">검증 손실</th><th scope="col" className="research-result-wide">결과 및 상태</th></tr></thead><tbody>{experiments.map(([version, train, validation, loss, result]) => <Fragment key={version}><tr className={version === "v5" ? "research-selected" : undefined}><th scope="row" id={`experiment-${version}`}>{version}</th><td>{train}</td><td>{validation}</td><td>{loss}</td><td className="research-result-wide">{result}</td></tr><tr className={`research-result-narrow ${version === "v5" ? "research-selected" : ""}`}><td colSpan={4} headers={`experiment-${version}`}>{result}</td></tr></Fragment>)}</tbody></table>
              <p className="research-table-note">v2~v5는 3 epochs로 학습했습니다. 검증 손실은 별도 검증 데이터에 대한 오차 지표로, 데이터 구성이 달라 이 수치만으로 응답 품질을 비교할 수 없습니다. 행동 평가는 AI가 작성한 기준에 따른 판정이며 사람 대상 실험이 아닙니다. <ExternalLink href={`${GITHUB}/blob/main/runpod/artifacts/kanana-performance-assessment-20260919/README.md`}>평가 기록</ExternalLink></p>
              <div className="research-findings"><div><h4>v5 선택 근거</h4><p>이전 평가에서 발견한 실패 유형을 보완했습니다. 새 프로세스에서 어댑터를 다시 불러오고 답변 5건의 생성 동작을 확인했습니다.</p></div><div><h4>검증되지 않은 범위</h4><p>v5의 독립 최종 평가와 vLLM 서빙 검증은 완료하지 않았습니다. 현재 데모를 아동 대상 공개 서비스 검증이 끝난 제품으로 볼 수 없습니다.</p></div></div>
              <div className="research-artifact"><div><h4>공개 어댑터</h4><p>저장소 루트는 v5이며, 이전 버전은 versions/ 경로에 보관합니다. 기본 모델 가중치와 서비스 검사 로직은 어댑터에 포함되지 않습니다.</p></div><ExternalLink href={`${HF}/tree/0880ce0372cedf22aec91b190f8a7b9499ccc176`}>릴리스 확인</ExternalLink></div>
            </div>
          </section>

          <section className="research-section" id="implementation" aria-labelledby="implementation-title">
            <div className="research-section-label"><span>04</span><h2 id="implementation-title">서비스 구현</h2><p>Interface & data handling</p></div>
            <div className="research-section-content">
              <h3>사용자가 확인하고 제어할 수 있는 기능</h3>
              <dl className="research-features">
                <div><dt>음성 및 텍스트 입력</dt><dd>최대 60초 동안 녹음할 수 있습니다. 인식된 문장을 확인한 뒤 전송하며, 키보드 입력도 지원합니다.</dd></div>
                <div><dt>연령별 응답 설정</dt><dd>4~6세와 7~10세 중 선택합니다. 연령을 변경하거나 새 대화를 시작하면 기존 대화 맥락을 초기화합니다.</dd></div>
                <div><dt>대화 기록과 다시 듣기</dt><dd>이전 답변을 기록에서 확인하고 다시 재생할 수 있습니다. 음성 재생은 사용자가 중지할 수 있습니다.</dd></div>
                <div><dt>대화 데이터 보관</dt><dd>최근 여섯 턴을 서버 메모리에 최대 한 시간 보관합니다. 서비스 서버는 녹음과 대화를 디스크에 저장하지 않습니다.</dd></div>
              </dl>
              <p className="research-data-note">음성 인식과 합성, 대체 응답에는 외부 API를 사용합니다. 해당 처리 과정에서 입력 데이터가 외부 제공자에게 전달됩니다. 민감한 개인정보는 입력하지 마세요.</p>
            </div>
          </section>

          <section className="research-closing" aria-labelledby="resources-title"><div><h2 id="resources-title">데모 및 공개 자료</h2><p>구현된 대화 흐름과 학습 결과를 직접 확인할 수 있습니다.</p></div><div className="research-actions"><a className="research-button" href="/chat">데모 실행 <span aria-hidden="true">↗</span></a><ExternalLink href={HF}>Hugging Face</ExternalLink><ExternalLink href={GITHUB}>GitHub</ExternalLink></div></section>
        </div>
      </main>
      <footer className="research-footer"><a href="/" aria-label="IRI 홈">iri</a><p>Kanana-based Korean conversational AI</p><span>Research prototype</span></footer>
    </div>
  );
}
