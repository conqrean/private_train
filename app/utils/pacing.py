# -*- coding: utf-8 -*-
"""예약 매크로의 요청 간격(페이싱) 정책.

서버의 자동화 탐지는 '얼마나 빠른가' 보다 '얼마나 규칙적인가' 를 먼저 본다.
예전에 쓰던 ``random.uniform(1, 1.5)`` 는 평균 1.25초에 분산이 거의 없는 띠라서,
요청 간격 히스토그램만 찍어도 사람과 구분된다. 그래서 기본값인 SAFE 모드는
사람의 새로고침 간격에 가까운 로그노멀(롱테일) 분포에 간헐적 연타와
자리비움 휴식을 섞는다.

RUSH 모드는 그 위장을 포기하고 속도를 택한다. 당일표나 출발 직전 취소표처럼
수십 분 안에 승부가 나는 상황에서 잠깐만 쓰는 것을 전제로 한 모드다.
"""
import math
import random
from dataclasses import dataclass
from datetime import datetime

SAFE = "safe"
RUSH = "rush"
DEFAULT_MODE = SAFE


@dataclass(frozen=True)
class PaceProfile:
    """한 모드의 간격 정책 묶음."""

    key: str
    label: str
    #: 로그노멀 중앙값(초)과 로그표준편차. ``uniform_range`` 가 있으면 쓰지 않는다.
    median: float
    sigma: float
    #: 어떤 경우에도 이보다 빠르게 서버를 찌르지 않는다.
    floor: float
    #: 설정하면 로그노멀 대신 이 구간의 균등분포를 쓴다.
    uniform_range: tuple[float, float] | None
    #: 사람처럼 몇 번 연달아 새로고침할 확률과, 그때의 횟수/간격.
    burst_chance: float
    burst_len: tuple[int, int]
    burst_delay: tuple[float, float]
    #: N회 시도마다 자리를 비운 것처럼 길게 쉰다. None 이면 쉬지 않는다.
    rest_every: tuple[int, int] | None
    rest_len: tuple[float, float]
    #: 취소표가 거의 안 나오는 심야(01~05시) 간격 배율.
    night_scale: float
    #: 예약을 시도했다 실패한 열차를 다시 건드리기까지의 대기 시간.
    retry_cooldown: tuple[float, float]
    #: 일시적 오류 지수 백오프 상한.
    max_backoff: float
    #: 사용자에게 보여줄 한 줄 설명.
    summary: str


PROFILES: dict[str, PaceProfile] = {
    SAFE: PaceProfile(
        key=SAFE,
        label="기본 모드",
        median=5.0,
        sigma=0.45,
        floor=3.0,
        uniform_range=None,
        burst_chance=0.15,
        burst_len=(1, 3),
        burst_delay=(2.8, 3.6),
        rest_every=(80, 150),
        rest_len=(40.0, 120.0),
        night_scale=3.0,
        retry_cooldown=(15.0, 30.0),
        max_backoff=60.0,
        summary="사람처럼 불규칙하게 조회 (평균 약 5초)",
    ),
    RUSH: PaceProfile(
        key=RUSH,
        label="긴급 모드",
        median=3.25,
        sigma=0.0,
        floor=1.5,
        uniform_range=(1.5, 5.0),
        burst_chance=0.0,
        burst_len=(0, 0),
        burst_delay=(1.5, 2.0),
        rest_every=None,
        rest_len=(0.0, 0.0),
        night_scale=1.0,
        retry_cooldown=(5.0, 10.0),
        max_backoff=20.0,
        summary="1.5~5초 무작위로 빠르게 조회 (당일표용)",
    ),
}


def normalize_mode(value: str | None) -> str:
    """폼/텔레그램에서 넘어온 값을 알려진 모드 키로 정규화한다."""
    return value if value in PROFILES else DEFAULT_MODE


class Pacer:
    """매크로 한 회차(run) 동안의 간격 상태를 들고 있는 객체.

    루프 바깥에서 한 번 만들어 두고 매 시도마다 :meth:`next_delay` 를 호출한다.
    연타 잔여 횟수·다음 휴식 시점·열차별 쿨다운이 전부 여기 모여 있어서,
    매크로 루프 쪽에는 정책이 새지 않는다.
    """

    def __init__(self, mode: str = DEFAULT_MODE):
        self.profile = PROFILES[normalize_mode(mode)]
        self._burst_left = 0
        self._next_rest = (
            random.randint(*self.profile.rest_every)
            if self.profile.rest_every
            else None
        )
        self._cooldowns: dict[str, float] = {}

    @property
    def mode(self) -> str:
        return self.profile.key

    @property
    def label(self) -> str:
        return self.profile.label

    def next_delay(self, attempt: int, now: datetime | None = None) -> tuple[float, str | None]:
        """다음 조회까지 쉴 시간과, 로그에 남길 사유를 돌려준다.

        :return: ``(초, 사유 또는 None)``
        """
        p = self.profile
        note: str | None = None

        if self._burst_left > 0:
            # 연타 진행 중
            self._burst_left -= 1
            delay = random.uniform(*p.burst_delay)
        elif p.burst_chance and random.random() < p.burst_chance:
            # 사람은 한 번 볼 때 두세 번 연달아 새로고침하고 한참 쉰다
            self._burst_left = random.randint(*p.burst_len)
            delay = random.uniform(*p.burst_delay)
        elif p.uniform_range:
            delay = random.uniform(*p.uniform_range)
        else:
            # 대부분 4~7초, 가끔 15초를 넘는 롱테일
            delay = random.lognormvariate(math.log(p.median), p.sigma)

        if self._next_rest is not None and attempt >= self._next_rest:
            self._next_rest = attempt + random.randint(*p.rest_every)
            pause = random.uniform(*p.rest_len)
            delay += pause
            note = f"잠시 쉬어갑니다 ({pause:.0f}초)"

        hour = (now or datetime.now()).hour
        if p.night_scale != 1.0 and 1 <= hour < 5:
            delay *= p.night_scale
            if note is None:
                note = "심야 시간대 - 조회 간격을 늘립니다"

        return max(p.floor, delay), note

    def hold_train(self, key: str, clock: float) -> None:
        """예약을 시도했다가 실패한 열차를 잠시 후보에서 뺀다.

        같은 열차에 예약 API 를 연타하는 것이 조회 연타보다 훨씬 강한 탐지
        신호이고, 방금 팔린 좌석이 1~2초 만에 다시 풀릴 일도 없다.
        """
        self._cooldowns[key] = clock + random.uniform(*self.profile.retry_cooldown)

    def is_held(self, key: str, clock: float) -> bool:
        """해당 열차가 아직 쿨다운 중인지."""
        return self._cooldowns.get(key, 0.0) > clock

    def backoff(self, consecutive_errors: int) -> float:
        """일시적 오류용 지수 백오프(지터 포함).

        고정 1초로 재시도하면 오류가 나는 동안에도 요청 빈도가 그대로라
        서버 입장에서는 가장 의심스러운 패턴이 된다.
        """
        base = min(2.0 ** max(0, consecutive_errors), self.profile.max_backoff)
        return base * random.uniform(0.8, 1.2)
