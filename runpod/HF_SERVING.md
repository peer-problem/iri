# Kanana 3B 어댑터 게시와 서빙

제품의 우선 답변 모델은 `kakaocorp/kanana-2-3b-instruct`와 이 프로젝트의 LoRA 어댑터다. 입력 및 출력 검사는 같은 Kanana 3B 원본 별칭으로 처리한다. GPU가 중지되거나 Kanana 요청이 실패하면 Luna high가 입력 검사부터 출력 검사까지 전체 경로를 다시 실행한다. Qwen 등 다른 개발 후보는 사용하지 않는다. 음성 인식과 음성 합성은 답변 모델과 별도 서비스다.

## 게시물

- Hugging Face 저장소: `peerproblem/Kanana-IRI-3B-QLoRA`
- 게시 커밋: `6eb9580da2e2e92875e30f6a6b41a7493fdccf15`
- 기본 모델 리비전: `6a5d7889964c4c590299d16e309eabab1f73f8a9`
- 어댑터 SHA-256: `7e65cf058a51407cef1a0526673253f30f5aafd4d2e192843e71516e43fe71d5`
- 로컬 원본: `runpod/backups/phase2-adapter-serving-v2.zip`
- 모델 카드: `runpod/model_card/README.md`

게시 파일은 어댑터 가중치와 설정, 검증 당시 토크나이저 파일, 모델 카드, 기본 모델의 라이선스 사본과 NOTICE다. 데이터셋, 검수 답변, 비밀키는 올리지 않는다. 라이선스는 [기본 모델의 고정 리비전](https://huggingface.co/kakaocorp/kanana-2-3b-instruct/blob/6a5d7889964c4c590299d16e309eabab1f73f8a9/LICENSE)을 따른다. 공개 UI에는 `Powered by Kanana`를 표시한다.

## GPU가 필요한 시점

개발과 문서 작업 중에는 Pod를 중지한다. 실제 서빙 검증이나 데모 시간에만 비용이 낮은 단일 GPU Pod를 시작한다. 시작 전 Runpod의 현재 GPU와 저장 단가, 예상 시간, 절대 중지 시각 및 중지 명령을 `.logs/`에 기록한다. 60분을 넘기지 않고 로컬 watchdog을 설정한다. 작업이 끝나면 결과를 영구 볼륨과 로컬에 백업하고 SHA-256을 대조한다. Pod의 `EXITED`를 Runpod에서 확인한다. 중지 후에도 남는 볼륨 비용을 기록한다.

## 모델 서버

GPU Pod에 저장소 코드를 배포하고 `runpod/requirements-gpu.txt`의 고정 vLLM 0.29.0을 설치한다. Hugging Face에서 게시 리비전을 고정해 어댑터 파일을 다운로드한다. 다운로드한 파일의 SHA-256을 위 값과 비교하고, 보관 중인 `training-manifest.json` 및 `policy.json`을 어댑터 폴더의 부모에 둔다. 학습 당시 정책과 현재 정책의 해시는 별도로 기록한다.

```sh
MODEL_PROFILE=kanana
MODEL_REVISION=6a5d7889964c4c590299d16e309eabab1f73f8a9
ADAPTER_NAME=iri-kanana3b-tuned
python -m runpod.operations.serve_model --adapter-run /workspace/iri-adapter-run --prefix-caching on --batch-invariant
```

`runpod/operations/serve_model.py`는 `127.0.0.1:8002`에만 바인딩한다. 서버 `/v1/models`에 원본 별칭 `kanana-<리비전>`과 어댑터 별칭 `iri-kanana3b-tuned`가 모두 있는지 확인한다. `runpod/operations/verify_serving.py`로 로딩 경로와 응답 모델을 검증한다.

## 제품 연결

Contabo의 `MODEL_PROFILE=kanana`, `MODEL_REVISION`, `ADAPTER_NAME=iri-kanana3b-tuned`, `MODEL_API_KEY`를 Pod와 일치시킨다. Contabo에서 Pod로 가는 인증된 HTTPS 엔드포인트 또는 `127.0.0.1:8002`에만 묶인 SSH 터널을 구성한다. 공개 HTTP 포트로 모델 서버를 노출하지 않는다. `GET /ready`가 원본과 어댑터의 실제 준비 상태를 확인하고, 준비된 동안 `POST /chat` 응답은 `provider: kanana`여야 한다. GPU가 중지되거나 연결이 끊기면 `/ready`는 503이고 `/chat`은 `provider: luna`로 응답한다. 두 답변 제공자가 모두 실패할 때만 503과 `provider: unavailable`을 반환한다.

개발자 컴퓨터를 거치는 짧은 데모에서는 아래의 두 SSH 연결을 각기 다른 터미널에서 유지할 수 있다. 첫 연결은 Pod의 로컬 모델 포트를 개발자 컴퓨터의 `18002`로 가져오고, 두 번째 연결은 그 포트를 Contabo의 로컬 `8002`로 전달한다. 실제 Pod 주소와 SSH 포트 및 VPS 계정은 당일 Runpod 및 Contabo 설정에서 확인한다. 개발자 컴퓨터가 연결을 유지해야 하므로 지속 운영에는 인증된 HTTPS 엔드포인트를 사용한다.

```sh
ssh -N -o ExitOnForwardFailure=yes -i .keys/runpod-ed25519 -p <POD_SSH_PORT> -L 127.0.0.1:18002:127.0.0.1:8002 root@<POD_HOST>
ssh -N -o ExitOnForwardFailure=yes -R 127.0.0.1:8002:127.0.0.1:18002 <VPS_USER>@<VPS_HOST>
```

두 연결이 열린 뒤 인증된 API의 `/ready`와 `/chat`을 확인한다. 터널 종료 또는 GPU 중지 후에는 `/ready`가 503으로 돌아가는지 확인한다. 운영 비밀키를 터널 명령이나 저장소 문서에 넣지 않는다.

지속 서빙은 GPU와 볼륨 요금이 계속 발생하므로 자동 상시 기동하지 않는다. 데모 기간을 정해 수동으로 켜고, 종료 시간에 백업 후 Pod를 중지한다. 웹과 API 배포만으로 GPU가 자동 시작되지는 않는다.

## 상태와 한계

2026-09-19에 공개 게시 파일을 새 A40 Pod로 다시 내려받아 가중치와 설정의 SHA-256을 확인했다. vLLM 0.29.0에서 원본과 어댑터 별칭의 로딩, 정책 해시 일치, 다섯 건의 생성 응답을 검증했다. 검증 보고서와 서버 로그 및 GPU 환경 기록은 `runpod/backups/phase3-hf-serving-20260919/`에 백업했고 원격 파일 해시와 대조했다. Pod는 `EXITED` 확인 후 삭제했다. 새 영구 볼륨은 없다.

Phase 2에서 어댑터의 개발 100문항 비교를 수행했다. 어댑터는 원본보다 정상 질문 점수가 낮아 당시 채택되지 않았다. 이번 완료 범위는 게시와 실제 서빙 검증, 중지 가능한 데모 운영 경로다. 최종 300문항 평가나 아동 대상 공개 출시 승인을 수행했다고 표시하지 않는다. 상시 GPU를 켜 두지 않으므로 데모를 시작할 때에는 위 제품 연결 단계에서 인증된 터널을 열고 `/ready`와 `/chat`을 다시 확인해야 한다.
