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

# Windows (PowerShell) - 권장
.\run.ps1  # 가상환경 생성 후 바로 실행 가능

# Windows (수동 가상환경 생성)
python -m venv venv
.\scripts\activate.ps1
```

**⚠️ 중요: 가상환경에서는 `python` 명령어를 사용하세요** (python3 아님!)

### 3. 의존성 설치

```bash
# Linux/macOS
pip install -r requirements.txt

# Windows
pip install -r requirements-windows.txt
```

---

## 실행

### 방법 1: 실행 파일 (가장 간단)

**Windows 사용자:**
```powershell
.\TrainReservationApp.exe
```
별도 설치 없이 바로 실행 가능합니다.

### 방법 2: 스크립트 실행 (개발자)

**빠른 실행:**
```powershell
.\run.ps1  # Windows
```

이 스크립트는 자동으로:
- 가상환경 활성화
- Python 캐시 삭제
- 애플리케이션 실행

**수동 실행:**
```bash
# 1. 가상환경 활성화
.\scripts\activate.ps1  # Windows
# source venv/bin/activate  # Linux/macOS

# 2. 실행 (python3 아님!)
python main.py
```

브라우저에서 `http://localhost:5050` 접속

---

## 트러블슈팅

### "ModuleNotFoundError: No module named 'flask'"

**원인**: `python3` 명령어가 시스템 Python을 가리킵니다.

**해결**:
```powershell
# python3 대신 python 사용
python main.py

# 또는 run.ps1 사용
.\run.ps1
```

### 코드 변경사항이 반영되지 않음

**원인**: Python 캐시 파일(.pyc)이 이전 코드를 캐시

**해결**:
```powershell
# 캐시 삭제
Get-ChildItem -Recurse -Include *.pyc,__pycache__ | Remove-Item -Recurse -Force

# 또는 run.ps1 사용 (자동 캐시 삭제)
.\run.ps1
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
| **SRT** | SRT 앱 → 승차권 확인 → 결제 |

### 3. 주의사항
- 예약 후 **결제 기한**(20분~1시간) 내 결제 필수
- 기한 내 결제 안 하면 **자동 취소**

---

## 프로젝트 구조

```
private_train/
├── app/                        # Flask 앱
│   ├── routes/                 # 라우트 (auth, search, reservation)
│   ├── services/               # 서비스 레이어 (SRT, Korail)
│   ├── templates/              # Jinja2 템플릿
│   └── static/                 # 정적 파일
├── SRT/                        # SRT API 모듈
├── korail2/                    # Korail API 모듈
├── build/                      # 빌드 스크립트
├── main.py                     # 진입점
└── requirements.txt            # 의존성
```

---

## 빌드 (실행파일 생성)

```bash
python build/build.py
```

**수동 빌드:**
```bash
# Windows
pyinstaller --onefile --add-data "app/templates;app/templates" --add-data "app/static;app/static" --name=TrainReservationApp main.py

# macOS / Linux
pyinstaller --onefile --add-data "app/templates:app/templates" --add-data "app/static:app/static" --name=TrainReservationApp main.py
```

---

## 라이선스

이 프로젝트는 개인 학습 목적으로만 사용하세요.
