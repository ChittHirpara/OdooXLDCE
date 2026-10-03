from datetime import datetime

import pytz

IST = pytz.timezone('Asia/Kolkata')

# 2026-10-05 is a Monday, 2026-10-06 a Tuesday, 2026-10-09 a Friday.
MON, TUE, FRI = 5, 6, 9


def club_dt(day, hour, minute=0):
    """Club-local (IST) wall time of October 2026 as a naive UTC datetime."""
    local = IST.localize(datetime(2026, 10, day, hour, minute))
    return local.astimezone(pytz.utc).replace(tzinfo=None)
