"""Read real metadata (name, version, icon) straight out of an APK file.

Uses androguard when it is installed. If parsing fails we just return None
and the bot falls back to the filename-based info.
"""
import logging

log = logging.getLogger(__name__)

try:
    from androguard.core.apk import APK as _AndroguarAPK  # type: ignore

    _HAS_ANDROGUARD = True
except Exception:  # pragma: no cover - optional dependency
    _HAS_ANDROGUARD = False


def parse_apk(path: str) -> dict | None:
    """Return {'label', 'version', 'package', 'icon_bytes'} or None."""
    if not _HAS_ANDROGUARD:
        return None
    try:
        apk = _AndroguarAPK(path)
        info = {
            "label": (apk.get_app_name() or "").strip() or None,
            "version": (apk.get_androidversion_name() or "").strip() or None,
            "package": (apk.get_package() or "").strip() or None,
            "icon_bytes": None,
        }
        try:
            icon = apk.get_app_icon(max_dpi=65536)
            if icon:
                with open(icon, "rb") as fh:
                    data = fh.read()
                if len(data) > 1024:
                    info["icon_bytes"] = data
        except Exception as exc:
            log.debug("apk icon extract failed: %s", exc)
        if info["label"] or info["version"]:
            return info
    except Exception as exc:
        log.warning("androguard parse failed: %s", exc)
    return None
