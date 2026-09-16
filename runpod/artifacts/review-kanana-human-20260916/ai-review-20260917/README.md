# 기존 모델 AI 평가 결과

팀원이 전달한 `ratings_a.csv`와 `ratings_b.csv` 원본을 보존했다. 전달 메시지에 따르면 GPT-5.6-sol을 각각 별도로 실행한 결과이며, 평가자 식별자는 `ai_gpt56sol_a`와 `ai_gpt56sol_b`다. 사람 두 명의 평가 결과는 아니다.

두 평가표는 상위 검수 패킷의 동일한 200개 익명 ID를 포함한다. 적용 대상 지표는 yes/no, 비대상 지표는 na인지 확인했다. 기존 원본 응답의 SHA-256도 매핑의 기록과 일치했다.

`summary.json`은 기존 집계 함수의 `review_kind="ai"`로 생성했다. `disagreements.csv`에는 유해 노출 2건, 정답 여부 7건, 연령 적합성 10건의 판정 불일치가 있다. 이는 지표별 불일치 수이며 서로 다른 시나리오 19개라는 뜻은 아니다. 미해결 판정이 있는 지표의 비율은 null로 보존했다.

대상은 학습 전 Kanana의 raw 100건과 guarded 100건이다. 학습 전후 비교 400건이나 학습본 채택 근거로 사용하지 않는다. 상위 `reviewer_a/ratings.csv`와 `reviewer_b/ratings.csv`는 빈 평가표로 유지한다.
