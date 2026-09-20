export type IllustrationKind = "conversation" | "adapter" | "inspection" | "age" | "memory";
export type DiagramLabel = { title: string; detail: string; at: [number, number, number]; tone?: string };
export const diagramContent: Record<IllustrationKind, { title: string; modes: string[]; notes: string[]; labels: DiagramLabel[] }> = {
  conversation: {
    title: "음성에서 답변까지, IRI의 대화 흐름",
    modes: ["음성 입력", "텍스트 입력"],
    notes: ["녹음한 음성은 전사문을 확인하고 수정한 뒤 전송합니다.", "키보드로 입력하면 음성 전사를 건너뛰고 같은 대화 하네스로 들어갑니다."],
    labels: [
      { title: "질문", detail: "마이크 / 키보드", at: [-4.5, -1.25, 0], tone: "blue" },
      { title: "전사문 확인", detail: "사용자가 수정 후 전송", at: [-1.85, -1.25, 0], tone: "blue" },
      { title: "대화 하네스", detail: "입력 검사 → 생성 → 출력 검사", at: [1.25, -1.25, 0], tone: "purple" },
      { title: "음성 답변", detail: "검사 후 TTS", at: [4.5, -1.25, 0], tone: "coral" },
    ],
  },
  adapter: {
    title: "QLoRA: 고정된 기본 모델과 학습하는 어댑터",
    modes: ["추론 경로", "학습 업데이트"],
    notes: ["입력 x는 기본 가중치 W와 LoRA 경로를 통과합니다. 두 결과를 더해 출력을 만듭니다.", "학습 예시의 정답과 예측을 비교한 손실로 A와 B를 갱신합니다. 기본 가중치 W는 고정합니다."],
    labels: [
      { title: "입력 x", detail: "대화 예시의 토큰", at: [-4.8, -.9, 0], tone: "blue" },
      { title: "W / FROZEN", detail: "4-bit 기본 가중치", at: [-1.1, 2.05, 0], tone: "blue" },
      { title: "A", detail: "저차원으로 투영", at: [-2.1, -1.7, 0], tone: "purple" },
      { title: "B", detail: "원래 차원으로 투영", at: [.5, -1.7, 0], tone: "coral" },
      { title: "합산", detail: "Wx + ΔWx", at: [3, -1.2, 0], tone: "green" },
      { title: "출력", detail: "ΔW = sBA", at: [4.8, 1.1, 0] },
      { title: "손실", detail: "예측과 정답 비교", at: [4.8, -1.55, 0], tone: "coral" },
      { title: "A/B 가중치 갱신", detail: "학습 시에만 적용", at: [0, -2.68, 0], tone: "coral" },
    ],
  },
  inspection: {
    title: "입력과 출력을 분리해서 검사하는 대화 하네스",
    modes: ["일반 답변", "입력 안내", "출력 차단", "대체 모델"],
    notes: ["입력 허용 → 어댑터 답변 생성 → 출력 허용 → 음성 합성 순서입니다.", "입력 검사에서 안내가 필요하다고 판단하면 일반 답변 생성을 건너뛰고 정책에 따른 안내를 반환합니다.", "생성한 답변을 출력 검사에서 차단하면 해당 답변을 전달하지 않고 정책에 따른 안내로 전환합니다.", "Kanana를 사용할 수 없으면 대체 모델이 입력 검사부터 생성과 출력 검사까지 다시 수행합니다."],
    labels: [
      { title: "입력 검사", detail: "기본 모델 + 제품 정책", at: [-4.3, 1.25, 0], tone: "green" },
      { title: "답변 생성", detail: "Kanana + IRI v5", at: [-1.35, 1.65, 0], tone: "purple" },
      { title: "출력 검사", detail: "기본 모델 + 제품 정책", at: [1.55, 1.25, 0], tone: "green" },
      { title: "전달", detail: "텍스트 + 음성", at: [4.45, 1.25, 0], tone: "coral" },
      { title: "정책 안내", detail: "안내 / 재질문 / 지원", at: [-3.15, -1.85, 0] },
      { title: "대체 모델 경로", detail: "입력 검사 → 생성 → 출력 검사", at: [1.4, -2, 0], tone: "blue" },
    ],
  },
  age: {
    title: "같은 질문에 적용하는 두 연령 설정",
    modes: ["4~6세", "7~10세"],
    notes: ["설정 설명용 예시: 쉬운 낱말과 짧은 문장으로 설명하는 것을 목표로 합니다. 실제 모델 응답이 아닙니다.", "설정 설명용 예시: 원인과 순서를 조금 더 자세히 설명하는 것을 목표로 합니다. 실제 모델 응답이 아닙니다."],
    labels: [
      { title: "연령 설정", detail: "프롬프트에 반영", at: [-3.1, -1.35, 0], tone: "purple" },
      { title: "답변 구성", detail: "어휘 / 설명 길이", at: [2.65, -1.35, 0], tone: "coral" },
    ],
  },
  memory: {
    title: "최근 여섯 턴만 남기는 대화 문맥",
    modes: ["대화 이어가기", "문맥 초기화"],
    notes: ["새 대화가 들어오면 오래된 턴부터 빠집니다. 최근 6턴은 서버 메모리에 최대 1시간 보관합니다.", "새 이야기 시작 또는 연령 변경 시 기존 문맥을 비웁니다. 대화와 녹음은 서비스 서버 디스크에 저장하지 않습니다."],
    labels: [
      { title: "이전 턴", detail: "최대 6턴 유지", at: [-3.9, -1.1, 0], tone: "blue" },
      { title: "서버 메모리", detail: "최대 1시간", at: [0, -1.1, 0], tone: "purple" },
      { title: "새 턴", detail: "오래된 순서로 교체", at: [3.9, -1.1, 0], tone: "coral" },
    ],
  },
};
