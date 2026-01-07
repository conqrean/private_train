# -*- coding: utf-8 -*-
"""Korail train service implementation."""
import sys
import os

# Add parent directory to path for korail2 module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from korail2 import Korail, KorailError, NeedToLoginError, SoldOutError, ReserveOption

from app.services.base_service import (
    BaseTrainService,
    TrainInfo,
    TrainProvider,
    SeatOption,
    ReservationResult
)

# Korail station list
KORAIL_STATIONS = [
    "서울", "용산", "광명", "천안아산", "오송", "대전", "김천(구미)", "신경주",
    "울산(통도사)", "부산", "공주", "익산", "정읍", "광주송정", "목포", "전주",
    "남원", "순천", "여천", "여수엑스포", "청량리", "양평", "원주", "제천",
    "단양", "풍기", "영주", "안동", "창원중앙", "창원", "마산", "진주", "홍성",
    "군산", "강릉", "만종", "둔내", "평창", "진부", "포항", "태화강"
]


class KorailService(BaseTrainService):
    """Korail train service implementation."""

    def __init__(self):
        self._client: Korail | None = None
        self._user_id: str | None = None
        self._password: str | None = None

    def login(self, user_id: str, password: str) -> bool:
        """Login to Korail."""
        try:
            self._client = Korail(user_id, password, auto_login=True, want_feedback=False)
            self._user_id = user_id
            self._password = password
            return self._client.logined
        except KorailError:
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
        include_no_seats: bool = False
    ) -> list[TrainInfo]:
        """Search for Korail trains."""
        if not self._client:
            raise NeedToLoginError()

        trains = self._client.search_train(
            dep=dep,
            arr=arr,
            date=date,
            time=time,
            include_no_seats=include_no_seats
        )

        return [self._to_train_info(t) for t in trains]

    def reserve(
        self,
        train: TrainInfo,
        seat_option: SeatOption = SeatOption.GENERAL_FIRST
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

            reservation = self._client.reserve(original_train, option=korail_option)

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
        except KorailError as e:
            return ReservationResult(
                success=False,
                message=str(e)
            )

    def get_stations(self) -> list[str]:
        """Get list of Korail stations."""
        return sorted(KORAIL_STATIONS)

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
