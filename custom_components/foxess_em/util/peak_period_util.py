""""Datetime utilities"""
from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta


class PeakPeriodUtils:
    """Peak Period Utils"""

    def __init__(self, eco_start_time: datetime, eco_end_time: datetime) -> None:
        """Init"""
        self._eco_start_time = eco_start_time
        self._eco_end_time = eco_end_time

    def in_peak(self, period: time):
        """In peak period"""
        return self._in_between(period, self._eco_start_time, self._eco_end_time)

    def next_eco_start(self) -> datetime:
        """Next eco start time"""
        now = datetime.now().astimezone()
        eco_start = now.replace(
            hour=self._eco_start_time.hour,
            minute=self._eco_start_time.minute,
            second=0,
            microsecond=0,
        )
        if now > eco_start:
            eco_start += timedelta(days=1)

        return eco_start

    def last_eco_start(self, period: datetime) -> datetime:
        """Last eco start time"""
        eco_start = period.replace(
            hour=self._eco_start_time.hour,
            minute=self._eco_start_time.minute,
            second=0,
            microsecond=0,
        )
        if eco_start > period:
            eco_start -= timedelta(days=1)

        return eco_start

    def next_eco_end(self, period: datetime) -> datetime:
        """Next eco end time"""
        eco_end = period.replace(
            hour=self._eco_end_time.hour,
            minute=self._eco_end_time.minute,
            second=0,
            microsecond=0,
        )
        if period > eco_end:
            eco_end += timedelta(days=1)

        return eco_end

    def _in_between(self, now: time, start: time, end: time):
        """In between two times"""
        if start <= end:
            return start < now <= end
        else:  # over midnight e.g., 23:30-04:15
            return now > start or now <= end

    def time_window(self) -> timedelta:
        """Calculate off-peak time window"""
        today = date.today()
        start = datetime.combine(today, self._eco_start_time)
        end = datetime.combine(today, self._eco_end_time)

        if start > end:
            end = end + timedelta(days=1)

        return end - start
