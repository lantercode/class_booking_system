"""P3-0 排期 display_status 纯派生边界测试。

derive_schedule_display_status 不查 DB / 不读 config（grace_minutes 注入），
全部场景靠 now 精确控制。
"""

from datetime import UTC, datetime, timedelta

from app.modules.schedule.models import ScheduleStatus
from app.modules.schedule.service import derive_schedule_display_status


def _schedule(*, start_delta, end_delta, db_status, grace_minutes=30, now=None):
    now = now or datetime.now(UTC)
    start_at = now + start_delta
    end_at = now + end_delta
    return derive_schedule_display_status(
        start_at=start_at,
        end_at=end_at,
        db_status=db_status,
        grace_minutes=grace_minutes,
        now=now,
    )


# ============================================================
# 业务取消：永远是 3，时间无关
# ============================================================


def test_cancelled_always_shows_three_regardless_of_time():
    future = datetime.now(UTC)
    past = datetime.now(UTC) - timedelta(hours=5)

    assert derive_schedule_display_status(
        start_at=future + timedelta(days=1),
        end_at=future + timedelta(days=1, hours=1),
        db_status=ScheduleStatus.CANCELLED.value,
        now=future,
    ) == 3

    assert derive_schedule_display_status(
        start_at=past - timedelta(hours=1),
        end_at=past,
        db_status=ScheduleStatus.CANCELLED.value,
        now=future,
    ) == 3


# ============================================================
# NORMAL + 时间已过：grace 到期前显示待上课，到期后显示已完成
# ============================================================


def test_normal_schedule_before_grace_keeps_pending():
    """刚结束 5 分钟，grace 30 分钟，还在宽限期内。"""
    now = datetime.now(UTC)
    assert derive_schedule_display_status(
        start_at=now - timedelta(hours=1),
        end_at=now - timedelta(minutes=5),
        db_status=ScheduleStatus.NORMAL.value,
        grace_minutes=30,
        now=now,
    ) == 1


def test_normal_schedule_after_grace_shows_completed():
    """结束 35 分钟，grace 30 分钟，应该算已完成。"""
    now = datetime.now(UTC)
    assert derive_schedule_display_status(
        start_at=now - timedelta(hours=1),
        end_at=now - timedelta(minutes=35),
        db_status=ScheduleStatus.NORMAL.value,
        grace_minutes=30,
        now=now,
    ) == 4


def test_normal_schedule_same_as_finished_status():
    """DB status=NORMAL 但时间已过 grace，显示必须等于 DB status=FINISHED。"""
    now = datetime.now(UTC)
    normal = derive_schedule_display_status(
        start_at=now - timedelta(hours=2),
        end_at=now - timedelta(hours=1),
        db_status=ScheduleStatus.NORMAL.value,
        grace_minutes=30,
        now=now,
    )
    finished = derive_schedule_display_status(
        start_at=now - timedelta(hours=2),
        end_at=now - timedelta(hours=1),
        db_status=ScheduleStatus.FINISHED.value,
        grace_minutes=30,
        now=now,
    )
    assert normal == finished == 4


# ============================================================
# 边界：end_at + grace_minutes == now（正好等于）
# ============================================================


def test_exact_end_of_grace_is_completed():
    """end_at + grace == now：左闭右开，应该算已完成。"""
    now = datetime.now(UTC)
    end_at = now - timedelta(minutes=30)  # end_at + 30min == now
    assert derive_schedule_display_status(
        start_at=now - timedelta(hours=1),
        end_at=end_at,
        db_status=ScheduleStatus.NORMAL.value,
        grace_minutes=30,
        now=now,
    ) == 4


def test_one_second_before_grace_end_is_still_pending():
    now = datetime.now(UTC)
    end_at = now - timedelta(minutes=29, seconds=59)  # 还差 1s
    assert derive_schedule_display_status(
        start_at=now - timedelta(hours=1),
        end_at=end_at,
        db_status=ScheduleStatus.NORMAL.value,
        grace_minutes=30,
        now=now,
    ) == 1


# ============================================================
# 上课中 / 待上课
# ============================================================


def test_ongoing_schedule_shows_two():
    assert _schedule(
        start_delta=timedelta(minutes=-10),
        end_delta=timedelta(minutes=50),
        db_status=ScheduleStatus.NORMAL.value,
    ) == 2


def test_future_schedule_shows_one():
    assert _schedule(
        start_delta=timedelta(days=1),
        end_delta=timedelta(days=1, hours=1),
        db_status=ScheduleStatus.NORMAL.value,
    ) == 1


def test_start_at_equal_now_is_ongoing():
    """正好到上课时间点：start_at == now，应该算上课中。"""
    now = datetime.now(UTC)
    assert derive_schedule_display_status(
        start_at=now,
        end_at=now + timedelta(hours=1),
        db_status=ScheduleStatus.NORMAL.value,
        grace_minutes=30,
        now=now,
    ) == 2


# ============================================================
# 空时间字段：退回 DB status 语义
# ============================================================


def test_none_times_fallback_to_db_status():
    assert derive_schedule_display_status(
        start_at=None,
        end_at=None,
        db_status=ScheduleStatus.FINISHED.value,
    ) == 4
    assert derive_schedule_display_status(
        start_at=None,
        end_at=None,
        db_status=ScheduleStatus.NORMAL.value,
    ) == 1


# ============================================================
# grace_minutes 为 0 时的立即切换
# ============================================================


def test_zero_grace_minutes_switches_to_completed_immediately():
    now = datetime.now(UTC)
    assert derive_schedule_display_status(
        start_at=now - timedelta(hours=1),
        end_at=now - timedelta(seconds=1),  # 刚过
        db_status=ScheduleStatus.NORMAL.value,
        grace_minutes=0,
        now=now,
    ) == 4
    assert derive_schedule_display_status(
        start_at=now + timedelta(hours=1),
        end_at=now + timedelta(hours=2),  # 还没开始
        db_status=ScheduleStatus.NORMAL.value,
        grace_minutes=0,
        now=now,
    ) == 1


# ============================================================
# 宽限期内 NORMAL vs FINISHED 可能不同：FINISHED 已经"过了"，
# NORMAL 可能还在 grace 内（业务上合理，宽限期给补写留时间）
# ============================================================


def test_finished_status_already_completed_even_within_grace():
    """DB status=FINISHED 是业务写入（schedule FINISHED 语义），
    不管时间是否还在 grace 内，都显示已完成。"""
    now = datetime.now(UTC)
    assert derive_schedule_display_status(
        start_at=now - timedelta(hours=1),
        end_at=now - timedelta(minutes=5),  # 刚结束，grace 30
        db_status=ScheduleStatus.FINISHED.value,
        grace_minutes=30,
        now=now,
    ) == 4  # 业务 FINISHED 直接算完成，不依赖宽限期
