# TSBookMaker

NotebookLM 스타일의 로컬 5-스튜디오 문서 가공 파이프라인. 한 챕터 분량의 PDF / TXT / MD 본문을 입력하면 LLM이 다섯 가지 마크다운 원고를 자동 생성한다.

[leedonwoo2827-ship-it/local-notebooklm](https://github.com/leedonwoo2827-ship-it/local-notebooklm) 의 플러그인 스튜디오 구조를 차용하되, 필요한 5개 스튜디오만 남기고 출력 형식을 마크다운으로 단순화했다.

## 5개 스튜디오

| # | 버튼 | 산출물 |
|---|---|---|
| ① | 앞부속 (학습목표·내용·가이드) | `chapter_intro.md` |
| ② | 단원학습정리 | `chapter_summary.md` |
| ③ | 학습평가 (정식) | `chapter_assessment.md` + `.xlsx` |
| ④ | 퀴즈 (보조) | `quiz.md` + `.xlsx` |
| ⑤ | 슬라이드 교안 30매 | `slide_deck.md` |

산출물은 모두 깨끗한 GFM 마크다운이며 워드프로세서로 그대로 가져갈 수 있다. 슬라이드 교안은 GPTs / Gemini Canvas 등 외부 도구의 입력으로 사용하기 좋다.

## 설치 및 실행

```bash
# Windows
setup.bat
# .env 를 열어 API 키 입력 후
run.bat

# macOS / Linux
./setup.sh
# .env 편집 후
./run.sh
```

브라우저에서 `http://localhost:8610` 접속.

## 작업 흐름

1. **노트북 생성** — 문서 묶음 하나에 노트북 하나
2. **소스 업로드** — 챕터별 PDF/TXT/MD 를 모두 업로드
3. **작업 대상 선택** — 작업할 소스의 체크박스만 켠다 (헤더에 `소스 1/N개` 표시)
4. **5버튼 클릭** — 산출물이 `data/notebooks/<노트북>/<청크>/` 에 생성
5. **모델 변경** — 디폴트 DeepSeek V4 → UI 상단 드롭다운으로 Claude Opus / GPT-4o 전환

## 원본 대비 변경점

- 스튜디오 5개로 축소: 앞부속 · 단원학습정리 · 학습평가 · 퀴즈 · 슬라이드 교안
- 모든 산출물 마크다운 출력 (HWPX / PPTX / PDF 렌더러 제거)
- LLM은 LiteLLM 프록시(포트 4610) 단일 라우팅, DeepSeek V4 디폴트
- 채팅 헤더 `소스 N개` 카운트 버그 수정 — 활성 소스 기준 `N/M` 표시, 0개일 때 스튜디오 버튼 자동 비활성화

## 포트

| 서비스 | 환경변수 | 기본값 |
|---|---|---|
| Streamlit UI | `TSB_UI_PORT` | 8610 |
| LiteLLM proxy | `TSB_LITELLM_PORT` | 4610 |
| FastAPI 내부 | `TSB_API_PORT` | 7613 |
| BGE-M3 embedding (선택) | `TSB_EMBED_PORT` | 7611 |
| faster-whisper STT (선택) | `TSB_STT_PORT` | 7612 |
| 노트북 인덱스 (선택) | `TSB_INDEX_PORT` | 7615 |

## 스튜디오 확장

새 스튜디오를 추가하려면:

1. `studio/<name>.py` 에 `StudioBase` 상속 클래스 작성
2. `prompts/<name>_ko.md` 에 프롬프트 작성 (`<<SYSTEM>>` / `<<USER>>` 구분자 사용)
3. `studio/registry.py` 의 `REGISTRY` 리스트에 등록

## 라이선스

MIT (예정)
