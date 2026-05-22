# TSBookMaker

NotebookLM 스타일의 로컬 5-스튜디오 문서 가공 도구. 한 챕터 분량의 PDF / TXT / MD / HWPX 본문을 입력하면 LLM이 다섯 가지 마크다운 원고를 자동으로 만들어 주고, **채팅으로 책 본문에 페이지 좌표 포함한 질의응답**이 가능합니다.

[leedonwoo2827-ship-it/local-notebooklm](https://github.com/leedonwoo2827-ship-it/local-notebooklm) 의 플러그인 스튜디오 구조를 차용하되, 필요한 5개 스튜디오만 남기고 출력 형식을 마크다운으로 단순화했습니다. 채팅은 **RAG-Anything + 로컬 BGE-M3 임베딩**으로 인덱싱해, 챕터별·책 전체 검색을 지원합니다. **터미널 명령을 모르는 사용자도 화면 좌측 ⚙ 설정 패널에서 API URL과 키만 입력하면 바로 쓸 수 있습니다.**

## 5개 스튜디오

| # | 버튼 | 산출물 |
|---|---|---|
| ① | 앞부속 (학습목표·내용·가이드) | `chapter_intro.md` |
| ② | 단원학습정리 | `chapter_summary.md` |
| ③ | 학습평가 (정식) | `chapter_assessment.md` + `.xlsx` |
| ④ | 퀴즈 (보조) | `quiz.md` + `.xlsx` |
| ⑤ | 슬라이드 교안 30매 | `slide_deck.md` |

산출물은 모두 깨끗한 GFM 마크다운이라 워드프로세서로 그대로 가져갈 수 있습니다. 슬라이드 교안은 GPTs / Gemini Canvas 등 외부 도구의 입력으로 사용하기 좋습니다.

## 설치 및 실행

### Windows
1. `setup.bat` 더블클릭 (Python 3.10–3.12 필요)
2. `run.bat` 더블클릭 → 브라우저가 자동으로 `http://localhost:8610` 열림

### macOS / Linux
```bash
./setup.sh
./run.sh
```

## 첫 사용 가이드 (5분)

1. 좌측 사이드바의 **⚙ API 설정**:
   - **API URL**: 예) `http://192.168.50.119:4000` (사내 LiteLLM 게이트웨이)
   - **API 키**: 회사 발급 virtual key
   - **모델 프리셋**: 💰 저렴 / ⚖ 균형 / 💎 프리미엄 중 클릭 (디폴트 저렴 = `deepseek-v4-flash`)
2. **🔌 연결 테스트** → OK 확인 후 **💾 저장**
3. **노트북 생성** → 챕터 PDF 업로드 → **자동 인덱싱 시작** (챕터당 30초~2분)
   - 최초 1회 BGE-M3 임베딩 모델 다운로드 (~2.3GB, HuggingFace 캐시)
4. **채팅** — 인덱싱이 끝나면 좌측 채팅창에 질문. 응답에 `[p.N]` 페이지 인용 포함
5. **🧰 Studio 5버튼** — 산출물이 `data/notebooks/<노트북>/<청크>/` 폴더에 저장

## 원본 대비 변경점

- 스튜디오 5개로 축소: 앞부속 · 단원학습정리 · 학습평가 · 퀴즈 · 슬라이드 교안
- 모든 산출물 마크다운 출력 (HWPX / PPTX / PDF 렌더러 제거)
- 키·URL·프리셋은 GUI 입력 (cmd / .env 편집 불필요)
- 채팅 헤더 `소스 N개` 카운트 버그 수정 — 활성 소스 기준 `N/M` 표시
- **채팅은 RAG-Anything 기반** — 챕터 단위 인덱싱, 책 페이지 좌표 보존, OCR 비활성
- 스튜디오는 풀 본문 기반 유지 — 챕터 통합 산출물 정확도 우선

## 설정 저장 위치

| 항목 | 위치 | 설명 |
|---|---|---|
| API URL/Key/모델 | `data/user_settings.json` | GUI 에서 저장 시 자동 생성. `.gitignore` 됨 |
| 작업 옵션 (포트, 문항 수 등) | `.env` (선택) | 기본값 그대로 두면 됨 |
| 산출물 | `data/notebooks/<노트북>/<청크>/` | 노트북·청크별 폴더 |

## 스튜디오 확장

새 스튜디오를 추가하려면:

1. `studio/<name>.py` 에 `StudioBase` 상속 클래스 작성
2. `prompts/<name>_ko.md` 에 프롬프트 작성 (`<<SYSTEM>>` / `<<USER>>` 구분자)
3. `studio/registry.py` 의 `REGISTRY` 리스트에 등록

## 라이선스

MIT — [LICENSE](LICENSE)
