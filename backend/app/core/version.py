"""System version and plugin API compatibility constants."""

# ── System Version ──
SYSTEM_VERSION = "0.2.0"
SYSTEM_VERSION_TUPLE = (0, 2, 0)

# ── Plugin API Contract ──
PLUGIN_API_VERSION = "1.0"          # Current plugin API contract version
COMPATIBLE_PLUGIN_API_RANGE = ">=1.0 <2.0"  # SemVer range for compatible plugins

# ── Plugin Manifest Schema Version ──
MANIFEST_SCHEMA_VERSION = 1         # Increment when plugin.json schema changes


def parse_version(version_str: str) -> tuple[int, ...]:
    """Parse a semVer string into a tuple of ints. Handles 'x' wildcards."""
    parts = []
    for p in version_str.strip().split("."):
        if p.lower() == "x" or p == "*":
            parts.append(-1)  # wildcard
        else:
            parts.append(int(p))
    return tuple(parts)


def version_matches(current: str, min_ver: str, max_ver: str) -> bool:
    """Check if current version is within [min_ver, max_ver] range.

    Supports SemVer ranges with 'x' wildcards (e.g., '1.x' matches 1.0-1.999).
    """
    cur = parse_version(current)

    # Check minimum
    mn = parse_version(min_ver)
    # Strip trailing zeros for comparison
    cur_cmp = cur[:len(mn)]
    if cur_cmp < mn:
        return False

    # Check maximum
    mx = parse_version(max_ver)
    # Handle wildcards: '1.x' means any 1.y
    if -1 in mx:
        # Wildcard: compare only up to the wildcard position
        fixed_len = mx.index(-1)
        if fixed_len > 0 and cur[:fixed_len] > mx[:fixed_len]:
            return False
    else:
        cur_cmp2 = cur[:len(mx)]
        if cur_cmp2 > mx:
            return False

    return True
