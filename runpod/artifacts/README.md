# 공유 검수 자료

이 폴더의 검수 자료는 Git으로 공유한다. 학습 결과 백업은 `runpod/backups/`에 로컬로 보관하며 Git에서 제외한다.

## 최신 Phase 2 결과

**Phase 2 종료 완료.** 원본 Kanana를 다음 단계 모델로 확정했다. [종료 보고서](phase2-evaluation-20260917/README.md)와 [Phase 3 인수인계](phase2-evaluation-20260917/phase3-handoff.md)를 확인한다. 아래의 기존 모델 200건 패킷은 새 학습 전후 비교 400건과는 다른 실행이다.

## 모델 답변 검수

`review-kanana-human-20260916/`은 기존 Kanana 모델의 답변을 검수하는 패킷이다. 개발 시나리오 100개를 raw와 guarded 경로로 실행한 총 200건이며, 학습 전후 비교 400건용 패킷은 아니다.

- 평가자 A: [검수 화면](review-kanana-human-20260916/reviewer_a/review.html), [빈 평가표](review-kanana-human-20260916/reviewer_a/ratings.csv)
- 평가자 B: [검수 화면](review-kanana-human-20260916/reviewer_b/review.html), [빈 평가표](review-kanana-human-20260916/reviewer_b/ratings.csv)

각 평가자는 자신의 폴더를 내려받아 `review.html`을 브라우저에서 연다. 화면의 판정 기준에 따라 같은 폴더의 `ratings.csv`에 평가자 식별자와 판정을 기록한다. 두 폴더는 같은 200건을 서로 다른 순서로 담고 있다. 두 평가자가 각각 전체를 독립적으로 평가한다.

프런티어 모델로 평가할 때도 해당 폴더의 두 파일을 함께 제공한다. AI 판정임을 알 수 있는 평가자 식별자를 사용하고, AI 평가를 사람의 독립 평가로 집계하지 않는다. 공유된 빈 평가표는 템플릿으로 유지하고 작성본은 별도로 전달한다.

`private/mapping.json`은 블라인드 ID와 원본 실행을 연결하는 취합 담당자용 자료이며, 팀에서 결과를 취합할 수 있도록 Git에 함께 포함한다. 독립 검수 중에는 자신의 `reviewer_a/` 또는 `reviewer_b/` 폴더를 사용하고 매핑은 결과 취합 단계에서 확인한다. 기존 AI 판정은 로컬 백업에 보존한다.

## 개발 시나리오 검수

[개발 데이터 검수표](dev-label-review-20260916/review.csv)는 개발 시나리오 100건의 기대 행동과 판정 기준을 검수하는 초안이다. 모델 답변 평가표와는 별개이며, 검수 완료 자료가 아니다.

## 보관 기준

공유할 HTML과 CSV 및 안내 문서는 이 폴더에 둔다. 모델 가중치와 체크포인트는 Git에서 제외한다. 전송용 압축 파일도 제외하며, 원본과 중복이면 무결성을 확인한 뒤 삭제한다. 과거 실행을 재현하는 데 필요한 백업은 `runpod/backups/`에 보관한다.
