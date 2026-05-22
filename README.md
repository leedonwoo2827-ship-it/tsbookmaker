# TSBookMaker

NotebookLM 스타일의 로컬 5-스튜디오 문서 가공 도구. 한 챕터 분량의 PDF / TXT / MD 본문을 입력하면 LLM이 다섯 가지 마크다운 원고를 자동으로 만들어 줍니다.

[leedonwoo2827-ship-it/local-notebooklm](https://github.com/leedonwoo2827-ship-it/local-notebooklm) 의 플러그인 스튜디오 구조를 차용하되, 필요한 5개 스튜디오만 남기고 출력 형식을 마크다운으로 단순화했습니다. **터미널 명령을 모르는 사용자도 화면 좌측 ⚙ 설정 패널에서 API URL과 키만 입력하면 바로 쓸 수 있습니다.**

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

1. 좌측 사이드바의 **⚙ API 설정**에서 입력:
   - **API 엔드포인트 URL**: 예) `https://llm.mycompany.com/v1` (회사 게이트웨이) 또는 `https://api.deepseek.com` (공식 DeepSeek)
   - **API 키**: 회사 발급 키 또는 본인이 발급받은 키
   - **모델 이름**: 예) `deepseek-v4` (담당자에게 문의)
   - **보조 모델** (선택): 콤마로 구분, 예) `claude-opus-4-7, gpt-4o`
2. **🔌 연결 테스트** 클릭 → "OK" 가 뜨면 정상
3. **💾 저장** 클릭 → 다음 실행부터는 자동으로 불러옴
4. 좌측 패널에서 **노트북 생성** → 작업할 챕터 PDF 업로드
5. 작업할 소스의 체크박스만 켜기 (헤더에 `소스 1/N개` 표시)
6. 우측 **🧰 Studio** 5버튼 클릭 → 산출물은 `data/notebooks/<노트북>/<청크>/` 폴더에 저장

## 원본 대비 변경점

- 스튜디오 5개로 축소: 앞부속 · 단원학습정리 · 학습평가 · 퀴즈 · 슬라이드 교안
- 모든 산출물 마크다운 출력 (HWPX / PPTX / PDF 렌더러 제거)
- **LiteLLM 프록시 제거 → Streamlit 한 프로세스로 단순화**, 키·URL 은 GUI 입력
- 채팅 헤더 `소스 N개` 카운트 버그 수정 — 활성 소스 기준 `N/M` 표시, 0개일 때 스튜디오 버튼 자동 비활성화

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
