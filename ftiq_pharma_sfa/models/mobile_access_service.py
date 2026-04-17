from .mobile_access_catalog import (
    MOBILE_PERMISSION_CATALOG,
    MOBILE_SCOPE_PAYLOAD_BUCKETS,
    empty_mobile_access_payload,
    mobile_full_key,
)


def build_mobile_access_payload(user):
    user.ensure_one()
    role = user._ftiq_mobile_role_value()
    payload = empty_mobile_access_payload(role=role)
    if not role:
        payload["reason"] = "missing_ftiq_role"
        return payload
    if not user.ftiq_mobile_access_enabled:
        payload["reason"] = "mobile_access_disabled"
        return payload
    profile = user.ftiq_mobile_access_profile_id
    if not profile:
        payload["reason"] = "missing_mobile_profile"
        return payload
    if profile.role != role:
        payload["reason"] = "profile_role_mismatch"
        return payload

    permission_map = profile.permission_map()
    payload["enabled"] = True
    payload["profile"] = {
        "id": profile.id,
        "name": profile.name,
        "code": profile.code,
    }
    payload["reason"] = ""
    for entry in MOBILE_PERMISSION_CATALOG:
        bucket_name = MOBILE_SCOPE_PAYLOAD_BUCKETS[entry["scope"]]
        if role not in entry["supported_roles"]:
            payload[bucket_name][entry["key"]] = False
            continue
        payload[bucket_name][entry["key"]] = bool(
            permission_map.get(mobile_full_key(entry["scope"], entry["key"]))
        )
    return payload
