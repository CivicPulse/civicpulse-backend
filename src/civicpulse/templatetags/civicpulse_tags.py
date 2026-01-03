"""
CivicPulse template tags and filters.

Usage in templates::

    {% load civicpulse_tags %}

    {% civicpulse_setting "SITE_NAME" %}
    {% civicpulse_use_compressor as use_compressor %}
"""

from django import template

from civicpulse.conf import civicpulse_settings

register = template.Library()


@register.simple_tag
def civicpulse_setting(name):
    """
    Get a CivicPulse setting value.

    Usage::

        {% civicpulse_setting "SITE_NAME" %}
        {% civicpulse_setting "CDN_HTMX" %}
    """
    return getattr(civicpulse_settings, name)


@register.simple_tag
def civicpulse_use_compressor():
    """
    Check if django-compressor should be used.

    Returns True only if USE_COMPRESSOR is True AND
    django-compressor is installed.

    Usage::

        {% civicpulse_use_compressor as use_compressor %}
        {% if use_compressor %}
            {% load compress %}
            {% compress css %}...{% endcompress %}
        {% else %}
            <link rel="stylesheet" href="...">
        {% endif %}
    """
    if not civicpulse_settings.USE_COMPRESSOR:
        return False
    try:
        import compressor  # noqa: F401

        return True
    except ImportError:
        return False


@register.simple_tag
def civicpulse_include_nav():
    """
    Check if default navigation should be included.

    Usage::

        {% civicpulse_include_nav as include_nav %}
        {% if include_nav %}
            {% include "civicpulse/partials/_navigation.html" %}
        {% endif %}
    """
    return civicpulse_settings.INCLUDE_DEFAULT_NAV
