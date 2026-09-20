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
  return <a href={href} target="_blank" rel="noreferrer">{children}<span className="sr-only"> (새 탭)</span></a>;
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
      <a className="research-skip" href="#abstract">본문으로 이동</a>
      <header className="paper-nav">
        <a href="/" aria-label="IRI 홈">IRI</a>
        <nav aria-label="페이지 메뉴"><a href="#system">시스템</a><a href="#evaluation">학습 및 평가</a><a href="/chat">데모 ↗</a></nav>
      </header>
      <main className="paper">
        <header className="paper-title">
          <h1>IRI: 아동을 위한 한국어 음성 대화 AI</h1>
          <p className="paper-subtitle">Kanana 기반 모델의 연령별 응답 학습과 음성 인터페이스 구현</p>
          <p className="paper-byline">IRI Project</p>
          <div className="paper-links"><a href="/chat">[데모]</a><ExternalLink href={HF}>[모델]</ExternalLink><ExternalLink href={GITHUB}>[코드]</ExternalLink></div>
        </header>

        <section className="paper-abstract" id="abstract" aria-labelledby="abstract-title">
          <h2 id="abstract-title">초록</h2>
          <p>IRI는 Kanana 2 3B Instruct에 QLoRA 어댑터를 적용한 한국어 음성 대화 연구 프로젝트다. 4~6세와 7~10세에 맞춘 응답을 목표로 하며, 입력 검사와 답변 생성 및 출력 검사를 음성 인터페이스에 연결했다. 다섯 차례 학습한 어댑터와 구현 코드를 공개한다. 현재 선택한 v5의 독립 최종 평가와 vLLM 서빙 검증은 미완료다.</p>
          <p className="paper-keywords"><strong>주요어:</strong> 한국어 대화, 연령별 응답, Kanana, QLoRA, 음성 인터페이스</p>
        </section>

        <div className="paper-columns intro-columns">
          <section aria-labelledby="scope-title"><h2 id="scope-title">1. 연구 범위</h2><p>기본 모델은 <span lang="en">Kanana 2 3B Instruct</span>다. QLoRA 추가 학습을 통해 연령에 맞는 어휘와 설명 길이를 조정한다. 입력과 출력 검사는 같은 원본 모델 및 제품 정책을 사용한다.</p><p>사용자는 음성 또는 텍스트로 질문하고 답변을 듣는다. 보호자는 연령 설정과 최근 대화 기록을 확인할 수 있다.</p></section>
          <section aria-labelledby="model-title"><h2 id="model-title">1.1. 모델 구성</h2><dl className="paper-specs"><div><dt>기본 모델</dt><dd>Kanana 2 3B Instruct</dd></div><div><dt>추가 학습</dt><dd>IRI v5 QLoRA</dd></div><div><dt>응답 연령</dt><dd>4~6세 / 7~10세</dd></div><div><dt>공개 산출물</dt><dd>어댑터 v1~v5 및 구현 코드</dd></div></dl></section>
        </div>

        <ResearchIllustration kind="conversation" paused={paused} caption="그림 1. 음성 입력과 전사문 확인, 답변 재생으로 구성된 대화 인터페이스." />

        <section id="system" className="paper-section" aria-labelledby="system-title">
          <h2 id="system-title">2. 추론 및 음성 처리</h2>
          <p>질문과 답변을 각각 검사한다. 검사 단계는 위험한 응답을 줄이기 위한 장치이며 모든 오류를 차단한다는 뜻은 아니다.</p>
          <table className="paper-table pipeline-table"><caption>표 1. 입력부터 음성 출력까지의 처리 절차</caption><thead><tr><th scope="col">단계</th><th scope="col">처리 내용</th><th scope="col">구성 요소</th></tr></thead><tbody>{steps.map(([stage, detail, runtime], i) => <tr key={stage}><th scope="row"><span className="step-index">{i + 1}.</span> {stage}</th><td>{detail}</td><td><code>{runtime}</code></td></tr>)}</tbody></table>
          <p className="paper-note"><strong>대체 경로.</strong> Kanana를 사용할 수 없으면 gpt-5.6-luna(high)가 입력 검사부터 전체 경로를 다시 수행한다. 실제 응답에 사용된 제공자는 대화 화면에 표시한다.</p>
        </section>

        <ResearchIllustration kind="inspection" paused={paused} caption="그림 2. 질문과 생성된 답변을 각각 검사하는 구성. 검사 통과가 모든 오류의 부재를 보장하지는 않는다." />

        <section id="evaluation" className="paper-section" aria-labelledby="evaluation-title">
          <h2 id="evaluation-title">3. 학습 및 평가</h2>
          <p>데이터를 보강하며 다섯 차례 어댑터를 학습했다. 표 2는 학습 및 평가 기록이며 제품 안전성이나 아동 대상 사용 적합성을 인증하는 지표가 아니다.</p>
          <table className="paper-table results-table"><caption>표 2. 버전별 학습 데이터 및 평가 기록</caption><thead><tr><th scope="col">버전</th><th scope="col">학습 수</th><th scope="col">검증 수</th><th scope="col">검증 손실</th><th scope="col" className="result-wide">결과 및 상태</th></tr></thead><tbody>{experiments.map(([version, train, valid, loss, result]) => <Fragment key={version}><tr className={version === "v5" ? "selected" : undefined}><th scope="row" id={`experiment-${version}`}>{version}</th><td>{train}</td><td>{valid}</td><td>{loss}</td><td className="result-wide">{result}</td></tr><tr className={`result-narrow ${version === "v5" ? "selected" : ""}`}><td colSpan={4} headers={`experiment-${version}`}>{result}</td></tr></Fragment>)}</tbody></table>
          <p className="paper-note">v2~v5는 3 epochs로 학습했다. 검증 데이터 구성이 달라 손실값만으로 응답 품질을 직접 비교할 수 없다. 행동 평가는 AI가 작성한 기준에 따른 판정이며 사람 대상 실험이 아니다. <ExternalLink href={`${GITHUB}/blob/main/runpod/artifacts/kanana-performance-assessment-20260919/README.md`}>[평가 기록]</ExternalLink></p>
          <div className="paper-columns findings"><section><h3>3.1. v5 선택 근거</h3><p>이전 평가에서 발견한 실패 유형을 보강했다. 새 프로세스에서 어댑터를 다시 불러 대표 답변 5건의 생성 동작을 확인했다.</p></section><section><h3>3.2. 검증 한계</h3><p>v5의 독립 최종 평가와 vLLM 서빙 검증은 완료하지 않았다. 현재 데모를 아동 대상 공개 서비스 검증이 끝난 제품으로 볼 수 없다.</p></section></div>
        </section>

        <ResearchIllustration kind="adapter" paused={paused} caption="그림 3. 기본 모델에 추가 학습한 어댑터를 적용하는 구성. 파라미터 크기 비율을 나타내지 않는다." />

        <section id="implementation" className="paper-section" aria-labelledby="implementation-title">
          <h2 id="implementation-title">4. 인터페이스 및 데이터 처리</h2>
          <table className="paper-table features-table"><caption>표 3. 사용자가 확인하고 제어할 수 있는 기능</caption><thead><tr><th scope="col">기능</th><th scope="col">지원 범위</th><th scope="col">사용자 제어</th></tr></thead><tbody>{features.map(([feature, scope, control]) => <tr key={feature}><th scope="row">{feature}</th><td>{scope}</td><td>{control}</td></tr>)}</tbody></table>
          <p className="paper-note">음성 인식과 합성 및 대체 응답에는 외부 API를 사용한다. 처리 과정에서 입력 데이터가 외부 제공자에게 전달된다. 민감한 개인정보는 입력하지 않아야 한다.</p>
        </section>

        <div className="paper-figure-pair">
          <ResearchIllustration kind="age" paused={paused} caption="그림 4. 두 연령대에 맞춘 어휘와 설명 길이 설정." />
          <ResearchIllustration kind="memory" paused={paused} caption="그림 5. 최근 여섯 턴의 메모리 보관과 1시간 만료." />
        </div>

        <section className="paper-section paper-resources" aria-labelledby="resources-title"><h2 id="resources-title">5. 공개 자료</h2><p>모델 저장소 루트에는 v5를, <code>versions/</code>에는 이전 버전을 보관한다. 기본 모델 가중치와 서비스 검사 로직은 어댑터에 포함되지 않는다.</p><ol><li><ExternalLink href={`${HF}/tree/0880ce0372cedf22aec91b190f8a7b9499ccc176`}>IRI QLoRA 어댑터 및 버전 기록.</ExternalLink> Hugging Face.</li><li><ExternalLink href={GITHUB}>IRI 구현 코드 및 평가 기록.</ExternalLink> GitHub.</li><li><a href="/chat">음성 및 텍스트 대화 데모.</a></li></ol></section>
        <footer className="paper-footer"><span>IRI / Research prototype</span><button type="button" aria-pressed={paused} onClick={() => setPaused(!paused)}>{paused ? "삽화 움직임 재개" : "삽화 움직임 멈추기"}</button></footer>
      </main>
    </div>
  );
}
