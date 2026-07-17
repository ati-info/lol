"""Assemble the decorated channel caption.

Look:
    📱 Remini - AI Photo Enhancer v3.8.1360 (Premium Unlocked) 🔓
    ━━━━━━━━━━━━━━━━━━━━┳═─
    🤖 𝗠𝗼𝗱 𝗜𝗻𝗳𝗼:
    ● Premium / paid features unlocked
    ● No ads
    ● ...
    ━━━━━━━━━━━━━━━━━━━━┹═─
    📦 𝗦𝗶𝘇𝗲: 93.6 MB • 📁 APK
    ✈️ 𝗕𝗮𝗰𝗸𝘂𝗽: https://t.me/xxxx
"""
from .utils import trim, ubold

_DIV_TOP = "━" * 20 + "┳═─"
_DIV_BOT = "━" * 20 + "┹═─"

MAX_FEATURES = 7
FEATURE_WIDTH = 110


def build_caption(
    *,
    name: str,
    version: str | None,
    features: list[str],
    size: str,
    ext: str,
    mod: bool,
    link: str | None,
) -> str:
    # ---- title line ----------------------------------------------------
    title = f"📱 {name}"
    if version:
        title += f" v{version}"
    if mod:
        title += " (Premium Unlocked) 🔓"

    header = (
        "🤖 " + ubold("Mod Info") + ":"
        if mod
        else "✨ " + ubold("Features") + ":"
    )

    lines = [title, _DIV_TOP, header]

    # ---- feature bullets ----------------------------------------------
    shown = 0
    for feat in features or []:
        feat = feat.strip().lstrip("•-—●*· ").strip()
        if not feat:
            continue
        lines.append(f"● {trim(feat, FEATURE_WIDTH)}")
        shown += 1
        if shown >= MAX_FEATURES:
            break
    if shown == 0:
        lines.append("● Free to use 🆓")

    # ---- footer ---------------------------------------------------------
    lines.append(_DIV_BOT)
    file_type = (ext or "").lstrip(".").upper() or "FILE"
    lines.append(f"📦 {ubold('Size')}: {size}  •  📁 {file_type}")
    if link:
        lines.append(f"✈️ {ubold('Backup')}: {link}")

    return trim("\n".join(lines), 980)
