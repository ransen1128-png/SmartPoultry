"""Who may change which account."""


def may_manage_account(administrator, target):
    """Only a superuser may disable, change or delete administrator accounts."""
    return administrator.is_superuser or not (target.is_staff or target.is_superuser)
