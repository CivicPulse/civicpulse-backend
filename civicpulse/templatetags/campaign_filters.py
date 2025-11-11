"""Custom template filters for campaign templates."""

from django import template

register = template.Library()


@register.filter(name="abs")
def absolute_value(value):
    """Return the absolute value of a number.

    Args:
        value: The number to get absolute value of

    Returns:
        The absolute value of the input

    Example:
        {{ -5|abs }} -> 5
        {{ 5|abs }} -> 5
    """
    try:
        return __builtins__["abs"](int(value))
    except (ValueError, TypeError):
        return value
