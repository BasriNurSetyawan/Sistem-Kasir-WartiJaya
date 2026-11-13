from datetime import datetime
from zoneinfo import ZoneInfo

from flask import current_app, has_app_context


def business_today():
    timezone_name = (
        current_app.config.get('BUSINESS_TIMEZONE', 'Asia/Jakarta')
        if has_app_context() else 'Asia/Jakarta'
    )
    return datetime.now(ZoneInfo(timezone_name)).date()
