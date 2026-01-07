# -*- coding: utf-8 -*-
"""SRT train service implementation."""
import sys
import os

# Add parent directory to path for SRT module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from SRT import SRT, SRTError, SRTNotLoggedInError
from SRT.constants import STATION_NAME
from SRT.seat_type import SeatType

from app.services.base_service import (
    BaseTrainService,
    TrainInfo,
    TrainProvider,
    SeatOption,
    ReservationResult
)


class SRTService(BaseTrainService):
    """SRT train service implementation."""

    def __init__(self):
        self._client: SRT | None = None
        self._user_id: str | None = None
        self._password: str | None = None

    def login(self, user_id: str, password: str) -> bool:
        """Login to SRT."""
        try:
            self._client = SRT(user_id, password, auto_login=True, verbose=False)
            self._user_id = user_id
            self._password = password
            return self._client.is_login
        except SRTError:
            return False

    def logout(self) -> None:
        """Logout from SRT."""
        if self._client:
            self._client.logout()
        self._client = None
        self._user_id = None
        self._password = None

    def is_logged_in(self) -> bool:
        """Check if logged in."""
        return self._client is not None and self._client.is_login

    def search(
        self,
        dep: str,
        arr: str,
        date: str,
        time: str,
        include_no_seats: bool = False
    ) -> list[TrainInfo]:
        """Search for SRT trains."""
        if not self._client:
            raise SRTNotLoggedInError()

        trains = self._client.search_train(
            dep=dep,
            arr=arr,
            date=date,
            time=time,
            available_only=not include_no_seats
        )

        return [self._to_train_info(t) for t in trains]

    def reserve(
        self,
        train: TrainInfo,
        seat_option: SeatOption = SeatOption.GENERAL_FIRST
    ) -> ReservationResult:
        """Reserve an SRT train."""
        if not self._client:
            return ReservationResult(
                success=False,
                message="로그인이 필요합니다."
            )

        try:
            # Convert seat option
            srt_seat_type = self._convert_seat_option(seat_option)

            # Get original train object from raw_data
            original_train = train.raw_data.get('_original')
            if not original_train:
                return ReservationResult(
                    success=False,
                    message="열차 정보를 찾을 수 없습니다."
                )

            reservation = self._client.reserve(original_train, special_seat=srt_seat_type)

            return ReservationResult(
                success=True,
                message="예약 성공!",
                reservation_id=reservation.reservation_number if reservation else None,
                details={'reservation': reservation}
            )
        except SRTError as e:
            return ReservationResult(
                success=False,
                message=str(e)
            )

    def get_stations(self) -> list[str]:
        """Get list of SRT stations."""
        return sorted(STATION_NAME.values())

    def _to_train_info(self, train) -> TrainInfo:
        """Convert SRT train to TrainInfo."""
        return TrainInfo(
            provider=TrainProvider.SRT,
            train_name=train.train_name,
            train_number=train.train_number,
            dep_date=train.dep_date,
            dep_time=train.dep_time,
            arr_date=train.arr_date,
            arr_time=train.arr_time,
            dep_station=train.dep_station_name,
            arr_station=train.arr_station_name,
            general_seat_available=train.general_seat_available(),
            special_seat_available=train.special_seat_available(),
            raw_data={'_original': train, **train.__dict__}
        )

    def _convert_seat_option(self, option: SeatOption) -> SeatType:
        """Convert SeatOption to SRT SeatType."""
        mapping = {
            SeatOption.GENERAL_FIRST: SeatType.GENERAL_FIRST,
            SeatOption.GENERAL_ONLY: SeatType.GENERAL_ONLY,
            SeatOption.SPECIAL_FIRST: SeatType.SPECIAL_FIRST,
            SeatOption.SPECIAL_ONLY: SeatType.SPECIAL_ONLY,
        }
        return mapping.get(option, SeatType.GENERAL_FIRST)
