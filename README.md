# jakal-math-generator

HWPX와 연동되는 수능 수학 문항 제작기용 오케스트레이션 레포다.

이 저장소의 verified 구현은 다음을 포함한다.

- HWPX 템플릿의 무손실 round-trip 로드/저장
- Codex CLI 기반 문항 생성 어댑터
- 생성 결과 검증 및 재시도 제어
- placeholder 기반 HWPX export 엔진
- 제품형 `ProductShellApp` 통합 계층

기본 원칙은 HWPX 구조 보존이다. 생성 성능보다 템플릿 안정성과 재현 가능한 Codex 실행 로그를 우선한다.

## Repository Layout

- `configs/codex/execution.json`: Codex CLI 실행 설정
- `prompts/codex/*.txt`: Codex 생성/복구 프롬프트 템플릿
- `src/contracts`: 문항 스펙, Codex 출력, 검증 결과 계약
- `src/generation`: Codex CLI adapter 및 재시도 제어
- `src/validation`: 형식, 정답 유일성, 정합성, 유사도 검사
- `src/hwpx`: HWPX archive round-trip 안전성 유틸리티
- `src/export`: placeholder 기반 HWPX export 엔진
- `desktop/src/product_shell`: 제품 통합 shell
- `tests`, `desktop/tests`: 계약/검증/round-trip/e2e 테스트
- `templates/hwpx`: export placeholder 계약

## Setup

1. Python 3.11 이상을 사용한다.
2. pytest를 설치한다.

```powershell
python -m pip install -U pytest
```

## Verification

전체 검증은 다음 명령으로 실행한다.

```powershell
python -m pytest
```

검증된 테스트 범위는 다음과 같다.

- HWPX no-op round-trip
- placeholder 치환 및 XML 안전성
- Codex CLI adapter 계약 및 재시도
- 생성 결과 검증
- retry controller
- product shell 통합 플로우

## Codex CLI Workflow

실제 문항 생성은 앱 내부 LLM 직접 호출이 아니라 Codex CLI adapter를 통해 수행한다.

핵심 흐름은 다음과 같다.

1. `GenerationForm`을 `QuestionSpec`으로 변환
2. `configs/codex/execution.json`을 읽어 Codex 실행 설정 구성
3. `prompts/codex/generation_prompt.txt` 또는 복구 프롬프트 조합
4. Codex CLI 실행
5. stdout을 JSON으로 파싱
6. validation/originality 검사
7. 통과한 결과만 HWPX export

Adapter가 남기는 아티팩트는 설정된 `artifacts_root` 아래의 시도별 디렉터리에 저장된다.

- `request.json`
- `stdout.log`
- `stderr.log`
- `run.log`
- `parsed_output.json` 또는 `parse_failure.log`

## Configuration

`configs/codex/execution.json`의 verified 필드는 다음과 같다.

- `mode`
- `command`
- `extra_args`
- `prompt_template_path`
- `repair_prompt_template_path`
- `artifacts_root`
- `timeout_seconds`
- `max_attempts`
- `enforce_json_only`

기본값은 `problem_generation` 모드이며 JSON 전용 응답을 강제한다.

## Product Shell

`desktop/src/product_shell/app.py`는 생성, 검증, export 상태를 분리해서 다루는 통합 계층이다.

지원되는 상태는 다음과 같다.

- `idle`
- `running`
- `codex_parse_failed`
- `validation_failed`
- `similarity_failed`
- `accepted`
- `export_failed`
- `export_succeeded`

예시는 `docs/desktop_shell.md`를 참고한다.

## Limitations

- 현재 구현은 Python 기반 orchestration shell과 HWPX export engine 중심이다.
- 별도 GUI 런처나 패키징 산출물은 이 closeout 시점에 포함되지 않는다.
- Codex CLI가 설치되어 있고 `configs/codex/execution.json`이 유효해야 실제 생성이 가능하다.
- export는 placeholder 기반 치환 방식이므로 템플릿에 필요한 token이 들어 있어야 한다.

## Reference Assets

- `2206~2609 평가원 문제모음(미적분).pdf`
- `평가원수학양식(수정) (1).hwpx`

이 자산들은 스타일/구조 참고용이며, 신규 문항 생성 과정에서 원문 재사용은 금지한다.
