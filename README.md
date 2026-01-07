# KTX/SRT 열차 예약 시스템

> **주의: 상업용, 영리행위 등 불법행위 절대 금지**
>
> 이 프로젝트는 개인 학습 목적으로만 사용하세요.

## 개요

SRT와 KTX(코레일) 열차를 통합하여 예약할 수 있는 웹 애플리케이션입니다.

### 주요 기능

- SRT / KTX 통합 예약
- 실시간 좌석 검색
- 자동 예약 시도 (매크로)
- 예약 성공 시 알림음
- 반응형 UI (Tailwind CSS)
- 크로스 플랫폼 지원 (Windows, macOS, Linux)

---

## 요구사항

- **Python**: 3.12+
- **Node.js**: 18+ (Tailwind CSS 빌드용, 선택사항)

---

## 설치

### 1. 저장소 클론

```bash
git clone <repository-url>
cd private_train
```

### 2. 가상환경 생성

```bash
# Linux/macOS
python3.12 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 3. 의존성 설치

```bash
# Linux/macOS
pip install -r requirements.txt

# Windows
pip install -r requirements-windows.txt
```

---

## 실행

### 통합 앱 (권장)

```bash
python main.py
```

브라우저에서 `http://localhost:5050` 접속

### 기존 앱 (레거시)

```bash
# SRT 전용
python srt_main_web.py

# KTX 전용
python ktx_main_web.py
```

---

## 사용 흐름

```
이 앱에서 예약 → 공식 앱에서 확인/결제
```

### 1. 이 앱에서 할 수 있는 것
- 로그인 (SRT/KTX 계정)
- 열차 검색
- 자동 예약 시도 (매크로)

### 2. 예약 성공 후
이 앱은 **예약만** 진행합니다. 예약 확인 및 결제는 **공식 앱**에서 해야 합니다.

| 서비스 | 확인 방법 |
|--------|----------|
| **KTX** | 코레일톡 앱 → 마이 → 예약내역 |
| **SRT** | SRT 앱 → MY → 예약 내역 |

### 3. 주의사항
- 예약 후 **결제 기한**(20분~1시간) 내 결제 필수
- 기한 내 결제 안 하면 **자동 취소**

---

## 프로젝트 구조

```
private_train/
├── app/                        # 통합 앱 (신규)
│   ├── __init__.py             # Flask 앱 팩토리
│   ├── config.py               # 설정
│   ├── routes/                 # 라우트
│   │   ├── auth.py             # 인증
│   │   ├── search.py           # 검색
│   │   └── reservation.py      # 예약
│   ├── services/               # 서비스 레이어
│   │   ├── base_service.py     # 추상 베이스
│   │   ├── srt_service.py      # SRT 서비스
│   │   └── korail_service.py   # Korail 서비스
│   ├── templates/              # Jinja2 템플릿
│   └── static/                 # 정적 파일
├── SRT/                        # SRT API 모듈
├── korail2/                    # Korail API 모듈
├── build/                      # 빌드 스크립트
├── main.py                     # 통합 앱 진입점
├── srt_main_web.py             # SRT 레거시 앱
├── ktx_main_web.py             # KTX 레거시 앱
├── requirements.txt            # 공통 의존성
└── requirements-windows.txt    # Windows 의존성
```

---

## 빌드

### 자동 빌드 (권장)

```bash
# 통합 앱 빌드
python build/build.py unified

# 모든 앱 빌드
python build/build.py all

# 빌드 대상 목록
python build/build.py --list
```

### 수동 빌드

**Windows:**
```bash
pyinstaller --onefile --add-data "app/templates;app/templates" --add-data "app/static;app/static" --hidden-import=flask --hidden-import=flask.sessions --name=TrainReservationApp main.py
```

**macOS / Linux:**
```bash
pyinstaller --onefile --add-data "app/templates:app/templates" --add-data "app/static:app/static" --hidden-import=flask --hidden-import=flask.sessions --name=TrainReservationApp main.py
```

빌드 결과물은 `dist/` 폴더에 생성됩니다.

---

## GitHub Actions

태그를 푸시하면 자동으로 Windows, macOS, Linux 빌드가 생성됩니다.

```bash
git tag v2.0.0
git push origin v2.0.0
```

---

## 개발

### Tailwind CSS 빌드 (선택사항)

```bash
# Node.js 의존성 설치
npm install

# CSS 빌드
npm run build:css

# 개발 모드 (파일 변경 감지)
npm run watch:css
```

> 참고: 개발 중에는 Tailwind CDN을 사용하므로 빌드가 필수는 아닙니다.

---

## 변경 이력

### v2.0.0
- SRT/KTX 통합 앱
- Tailwind CSS UI
- Python 3.12 지원
- 크로스 플랫폼 빌드 지원
- 서비스 추상화 레이어

### v1.0.0
- 초기 버전
- SRT/KTX 분리 앱

---

## 라이선스

이 프로젝트는 개인 학습 목적으로만 사용하세요.
