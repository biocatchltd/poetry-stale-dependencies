from datetime import timedelta


def render_timedelta(td: timedelta) -> str:
    if td.days >= 365:
        if td.days % 365 >= 30:
            return f"{td.days // 365}y {td.days % 365 // 30}mo"
        return f"{td.days // 365}y"
    if td.days >= 30:
        return f"{td.days // 30}mo"
    return f"{td.days}d"
