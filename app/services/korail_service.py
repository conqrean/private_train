# -*- coding: utf-8 -*-
"""Korail train service implementation."""
import sys
import os
import time
from time import sleep as _sleep
from datetime import datetime, timedelta

# Add parent directory to path for korail2 module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import requests

from korail2 import Korail, KorailError, NeedToLoginError, SoldOutError, NoResultsError, ReserveOption, AdultPassenger, BlockedError
from SRT.constants import STATION_NAME as SRT_STATION_NAME

from app.services.base_service import (
    BaseTrainService,
    TrainInfo,
    TrainProvider,
    SeatOption,
    ReservationResult
)
from app.services.stations import KORAIL_STATIONS, SRT_STATION_ALIASES

# Merged SRT+Korail station list, shown identically on both tabs (see srt_service.py
# for the same union). Note: some stations are provider-exclusive (e.g. 수서/동탄 are
# SRT-only, not served by KTX at all) - selecting one on the "wrong" tab will just
# come back with no search results.
ALL_STATIONS = sorted(
    set(KORAIL_STATIONS)
    | (set(SRT_STATION_NAME.values()) - set(SRT_STATION_ALIASES.values()))
)


class KorailService(BaseTrainService):
    """Korail train service implementation."""

    def __init__(self):
        self._client: Korail | None = None
        self._user_id: str | None = None
        self._password: str | None = None
        self.last_error: str | None = None

    def login(self, user_id: str, password: str) -> bool:
        """Login to Korail."""
        self.last_error = None
        try:
            self._client = Korail(user_id, password, auto_login=True, want_feedback=False)
            self._user_id = user_id
            self._password = password
            return self._client.logined
        except BlockedError as e:
            # 코레일 안티매크로에 막힌 경우. 아이디/비밀번호 문제가 아니므로
            # 자격증명 오류와 구분해서 알려준다.
            self.last_error = (
                "코레일 서버가 요청을 차단했습니다. 잠시 후 다시 시도해주세요. "
                "(서버 응답: %s)" % e.msg
            )
            return False
        except KorailError as e:
            self.last_error = str(e)
            return False
        except requests.RequestException as e:
            self.last_error = "코레일 서버에 연결할 수 없습니다: %s" % e
            return False

    def logout(self) -> None:
        """Logout from Korail."""
        if self._client:
            self._client.logout()
        self._client = None
        self._user_id = None
        self._password = None

    def is_logged_in(self) -> bool:
        """Check if logged in."""
        return self._client is not None and self._client.logined

    def search(
        self,
        dep: str,
        arr: str,
        date: str,
        time: str,
        include_no_seats: bool = False,
        max_pages: int = 2
    ) -> list[TrainInfo]:
        """
        Search for Korail trains with pagination-like logic.
        Fetches approx 10 trains per page, up to ``max_pages`` pages.
        """
        if not self._client:
            raise NeedToLoginError()

        all_trains = []
        current_time = time
        
        # Korail returns ~10 trains per call
        max_pages = max(1, max_pages)
        for page in range(max_pages):
            try:
                trains = self._client.search_train(
                    dep=dep,
                    arr=arr,
                    date=date,
                    time=current_time,
                    include_no_seats=include_no_seats
                )
                
                if not trains:
                    break
                    
                all_trains.extend(trains)

                # 마지막 페이지 뒤에는 쉬지 않는다 - 바로 루프를 빠져나갈 참이라
                # 예전 코드의 1.5초는 매 회차 그냥 버려지는 시간이었다.
                if page == max_pages - 1:
                    break

                # Add 1.5 second delay to avoid rate limiting (max 40 API calls per minute)
                _sleep(1.5)

                # Update time for next page
                # Parse last train time and add 1 minute
                last_train = trains[-1]
                last_dt = datetime.strptime(f"{last_train.dep_date}{last_train.dep_time}", "%Y%m%d%H%M%S")
                next_dt = last_dt + timedelta(minutes=1)
                current_time = next_dt.strftime("%H%M%S")
                
                # If next page query time goes to next day, stop
                if next_dt.strftime("%Y%m%d") != date:
                    break
                    
            except NoResultsError:
                # 결과 없음은 정상적인 페이지네이션 종료 조건.
                break
            except (KorailError, requests.RequestException):
                # 차단·로그인 만료·네트워크 오류는 삼키지 않는다. 예전에는 bare
                # except 가 이걸 전부 먹어버려서, 차단된 상태에서도 매크로가 빈
                # 결과를 "열차를 찾을 수 없음" 으로 표시하며 무한히 돌았다.
                # 첫 페이지부터 실패했으면 호출부(매크로 복구 로직)가 알아야 하고,
                # 이미 받아둔 페이지가 있으면 그것까지는 살려서 돌려준다.
                if not all_trains:
                    raise
                break

        return [self._to_train_info(t) for t in all_trains]

    def reserve(
        self,
        train: TrainInfo,
        seat_option: SeatOption = SeatOption.GENERAL_FIRST,
        passenger_count: int = 1
    ) -> ReservationResult:
        """Reserve a Korail train."""
        if not self._client:
            return ReservationResult(
                success=False,
                message="로그인이 필요합니다."
            )

        try:
            # Convert seat option
            korail_option = self._convert_seat_option(seat_option)

            # Get original train object from raw_data
            original_train = train.raw_data.get('_original')
            if not original_train:
                return ReservationResult(
                    success=False,
                    message="열차 정보를 찾을 수 없습니다."
                )

            passengers = [AdultPassenger(count=passenger_count)]
            reservation = self._client.reserve(original_train, passengers=passengers, option=korail_option)

            return ReservationResult(
                success=True,
                message="예약 성공!",
                reservation_id=reservation.rsv_id if reservation else None,
                details={'reservation': reservation}
            )
        except SoldOutError:
            return ReservationResult(
                success=False,
                message="매진되었습니다."
            )
        except BlockedError:
            # 차단은 "예약 실패" 가 아니라 "그만 보내라" 는 신호다. KorailError 로
            # 뭉뚱그려 실패 결과로 돌려주면 매크로가 이걸 매진처럼 취급해서 계속
            # 재시도한다. 호출부가 판단할 수 있게 그대로 올린다.
            raise
        except KorailError as e:
            return ReservationResult(
                success=False,
                message=str(e)
            )

    def get_stations(self) -> list[str]:
        """Get merged SRT+Korail station list (see ALL_STATIONS note above)."""
        return ALL_STATIONS

    def pay_with_card(
        self,
        reservation,
        card_number: str,
        card_password: str,
        validation_number: str,
        card_expire: str,
        installment: int = 0,
        card_type: str = "J",
    ) -> ReservationResult:
        """Pay for a Korail reservation with a credit card."""
        if not self._client:
            return ReservationResult(success=False, message="로그인이 필요합니다.")

        try:
            success = self._client.pay_with_card(
                reservation,
                card_number,
                card_password,
                validation_number,
                card_expire,
                installment,
                card_type,
            )
            if success:
                return ReservationResult(success=True, message="결제 완료!")
            return ReservationResult(success=False, message="결제에 실패했습니다.")
        except BlockedError:
            raise
        except KorailError as e:
            return ReservationResult(success=False, message=str(e))

    def _to_train_info(self, train) -> TrainInfo:
        """Convert Korail train to TrainInfo."""
        return TrainInfo(
            provider=TrainProvider.KORAIL,
            train_name=train.train_type_name,
            train_number=train.train_no,
            dep_date=train.dep_date,
            dep_time=train.dep_time,
            arr_date=train.arr_date,
            arr_time=train.arr_time,
            dep_station=train.dep_name,
            arr_station=train.arr_name,
            general_seat_available=train.has_general_seat(),
            special_seat_available=train.has_special_seat(),
            raw_data={'_original': train}
        )

    def _convert_seat_option(self, option: SeatOption) -> str:
        """Convert SeatOption to Korail ReserveOption."""
        mapping = {
            SeatOption.GENERAL_FIRST: ReserveOption.GENERAL_FIRST,
            SeatOption.GENERAL_ONLY: ReserveOption.GENERAL_ONLY,
            SeatOption.SPECIAL_FIRST: ReserveOption.SPECIAL_FIRST,
            SeatOption.SPECIAL_ONLY: ReserveOption.SPECIAL_ONLY,
        }
        return mapping.get(option, ReserveOption.GENERAL_FIRST)
