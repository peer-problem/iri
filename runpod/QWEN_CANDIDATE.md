# Phase 3 대체 기반 모델 개발 후보

기존 고정 Kanana의 개발 직접 검수에서 정상 정답과 지원 적절성 목표를 넘지 못했다. 같은 안전 정책 아래 모델 능력의 한계를 분리해 보기 위해 `Qwen/Qwen3-4B-Instruct-2507`을 개발 후보로 추가했다. 기본 `MODEL_PROFILE=kanana`와 서비스 정책은 바꾸지 않는다. 후보 리비전은 `cdbee75f17c01a7cc42f958dc650907174af0554`로 고정한다.

[Qwen 공식 모델 카드](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)는 이 모델을 비추론 4B 모델로 설명하고 vLLM 서빙을 지원한다. [라이선스](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/blob/main/LICENSE)는 Apache 2.0이다. 모델 카드의 비추론 권장 설정인 temperature 0.7, top_p 0.8, top_k 20을 생성에 적용하고 seed 42를 고정한다. 입력 및 출력 검사의 JSON 판정은 temperature 0과 seed 42로 유지한다. 모델과 샘플링 및 코드 해시를 결과 메타데이터에 기록한다.

검증 순서는 GPU 한 대에서 연결 확인, 검수된 개발 100문항의 raw 및 guarded 결과 200건, Codex의 답변 원문 직접 판정, 같은 장비의 Kanana baseline 비교다. 안전과 정답 및 지연 기준을 모두 대조한 뒤에만 후보를 채택한다. 이 후보를 평가하는 동안 잠긴 최종 300문항은 열어 보거나 모델 수정에 사용하지 않는다. 개발 실패 시 최종 모델로 고정하거나 최종 평가 600건을 실행하지 않는다.

실행 예시:

```sh
MODEL_PROFILE=qwen3_4b_instruct_2507 \
MODEL_REVISION=cdbee75f17c01a7cc42f958dc650907174af0554 \
python -m runpod.operations.serve_model --prefix-caching on --batch-invariant

MODEL_PROFILE=qwen3_4b_instruct_2507 \
MODEL_REVISION=cdbee75f17c01a7cc42f958dc650907174af0554 \
python -m runpod.operations.evaluate \
  --data runpod/data/prepared/dev-project-reviewed-v2/dev.jsonl \
  --mode both --output runpod/runs/qwen3-4b-candidate
```

Runpod 실행 전 GPU 및 저장 비용과 중지 계획을 `.logs/phase3-quality.md`에 적는다. 실행 후 원본을 영구 볼륨과 로컬에 백업하고 해시를 대조한 뒤 실제 EXITED 상태를 확인한다.
