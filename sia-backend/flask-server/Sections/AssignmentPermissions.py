from fnmatch import fnmatch


EVENT_VISIBILITY_PERMISSION = {
    "public": None,
    "member": "events.member",
    "student": "events.student",
    "private": "events.private",
}

REGISTRATION_VISIBILITY_PERMISSION = {
    "public": None,
    "member": "events.register.member",
    "student": "events.register.student",
    "private": "events.register.private",
}

TASK_VISIBILITY_PERMISSION = {
    "public": "events.public",
    "member": "task.help.member",
    "student": "task.help.student",
    "private": "task.help.private",
}


def has_permission(grants, required):
    """Use the same grant-pattern semantics as permissions.hasPermissions."""
    return any(fnmatch(required, grant) for grant in (grants or []))


def can_view_event(grants, event_visibility):
    if event_visibility not in EVENT_VISIBILITY_PERMISSION:
        return False
    required = EVENT_VISIBILITY_PERMISSION[event_visibility]
    return required is None or has_permission(grants, required)


def can_assign_to(grants, event_visibility, kind, target_visibility=None):
    if not can_view_event(grants, event_visibility):
        return False

    if kind == "registration":
        if target_visibility not in REGISTRATION_VISIBILITY_PERMISSION:
            return False
        required = REGISTRATION_VISIBILITY_PERMISSION[target_visibility]
        return required is None or has_permission(grants, required)
    if kind == "shift":
        return has_permission(grants, "events.help")
    if kind == "task":
        required = TASK_VISIBILITY_PERMISSION.get(target_visibility)
        return bool(required and has_permission(grants, required))
    return False
