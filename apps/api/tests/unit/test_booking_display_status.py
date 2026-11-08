"""我的预约 display_status：必须以排期时间为准，不能被提前签到/完成或历史脏数据带偏。"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.modules.booking.models import BookingStatus
from app.modules.booking.service import BookingService


def _booking(status: int) -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=1,
        public_id=uuid4(),
        tenant_id=1,
        schedule_id=10,
        student_id=2,
        status=status,
        source="self",
        membership_card_id=None,
        booked_at=now,
        cancelled_at=None,
        cancelled_reason=None,
        checked_in_at=None,
        created_at=now,
        updated_at=now,
    )


def _display(status: int, *, start_delta: timedelta | None, end_delta: timedelta | None) -> int:
    now = datetime.now(UTC)
    schedule_info: dict[str, datetime] = {}
    if start_delta is not None:
        schedule_info["start_at"] = now + start_delta
    if end_delta is not None:
        schedule_info["end_at"] = now + end_delta

    response = BookingService()._to_response(_booking(status), schedule_info=schedule_info)
    return response.display_status


@pytest.mark.parametrize(
    "status",
    [BookingStatus.BOOKED.value, BookingStatus.CHECKED_IN.value, BookingStatus.COMPLETED.value],
)
def test_future_schedule_never_shows_ongoing_or_completed(status):
    """时间没到：无论 DB 状态是已预约/已签到/已完成，都只能显示待上课。"""
    assert _display(
        status,
        start_delta=timedelta(days=2),
        end_delta=timedelta(days=2, hours=1),
    ) == 1


@pytest.mark.parametrize("status", [BookingStatus.BOOKED.value, BookingStatus.CHECKED_IN.value])
def test_ongoing_schedule_shows_in_class(status):
    assert _display(
        status,
        start_delta=timedelta(minutes=-10),
        end_delta=timedelta(minutes=50),
    ) == 3


@pytest.mark.parametrize("status", [BookingStatus.BOOKED.value, BookingStatus.CHECKED_IN.value])
def test_past_schedule_shows_completed(status):
    """历史脏数据里残留的“上课中”必须收口为已完成。"""
    assert _display(
        status,
        start_delta=timedelta(days=-30),
        end_delta=timedelta(days=-30, hours=1),
    ) == 4


def test_completed_booking_in_ongoing_window_stays_completed():
    assert _display(
        BookingStatus.COMPLETED.value,
        start_delta=timedelta(minutes=-10),
        end_delta=timedelta(minutes=50),
    ) == 4


def test_cancelled_booking_always_shows_cancelled():
    assert _display(
        BookingStatus.CANCELLED.value,
        start_delta=timedelta(days=2),
        end_delta=timedelta(days=2, hours=1),
    ) == 2


def test_without_schedule_time_falls_back_to_booking_status():
    assert _display(
        BookingStatus.CHECKED_IN.value,
        start_delta=None,
        end_delta=None,
    ) == 3
    assert _display(
        BookingStatus.BOOKED.value,
        start_delta=None,
        end_delta=None,
    ) == 1
