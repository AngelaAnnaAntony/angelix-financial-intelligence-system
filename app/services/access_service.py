from flask_login import current_user


def require_member(org_id):
    """
    Verify that the currently authenticated user belongs to
    the requested organization.

    Angelix currently stores the user's organization directly
    in users.organization_id rather than using a separate
    organization_members table.
    """

    if not current_user.is_authenticated:
        raise PermissionError("Authentication required.")

    if current_user.organization_id is None:
        raise PermissionError("User is not assigned to an organization.")

    try:
        requested_org_id = int(org_id)
    except (TypeError, ValueError):
        raise PermissionError("Invalid organization ID.")

    if current_user.organization_id != requested_org_id:
        raise PermissionError("Organization access denied.")

    return current_user.organization