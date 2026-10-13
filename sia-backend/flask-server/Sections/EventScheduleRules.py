"""Shared schedule shifting for event moves."""


def shift_event_schedule(event, difference, shifts=(), registration_windows=(), tasks=()):
    """Move the event end and all related times by the same delta.

    Fields without a value stay empty; the returned counts list only rows
    that actually had at least one time moved.
    """
    moved = {"shifts": 0, "registration_windows": 0, "tasks": 0}
    if event is not None and event.end:
        event.end += difference
    for shift in shifts:
        touched = False
        if shift.start:
            shift.start += difference
            touched = True
        if shift.end:
            shift.end += difference
            touched = True
        if touched:
            moved["shifts"] += 1
    for window in registration_windows:
        touched = False
        if window.start:
            window.start += difference
            touched = True
        if window.end:
            window.end += difference
            touched = True
        if touched:
            moved["registration_windows"] += 1
    for task in tasks:
        touched = False
        if task.deadline:
            task.deadline += difference
            touched = True
        if task.timeframe_start:
            task.timeframe_start += difference
            touched = True
        if task.timeframe_end:
            task.timeframe_end += difference
            touched = True
        if touched:
            moved["tasks"] += 1
    return moved
