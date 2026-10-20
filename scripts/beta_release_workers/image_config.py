"""Flatten reviewed app files without inheriting an ever-growing layer chain."""
import json
import re


def docker_value(value):
    # Dockerfile interpolation is distinct from shell interpolation.
    return json.dumps(value, ensure_ascii=False).replace("$", "\\$")


def final_image_config(base, *, release, commit, base_image, managed_kind="app-release-v1"):
    expected = {**base}
    expected["Env"] = [entry for entry in base.get("Env", []) if not entry.startswith("BUILD_ID=")]
    expected["Env"].append("BUILD_ID=" + release)
    expected["Labels"] = {
        **(base.get("Labels") or {}),
        "org.opencontainers.image.revision": commit,
        "smako.managed": managed_kind,
        "smako.release.base_image": base_image,
    }
    return expected


def flatten_instructions(config):
    # These uncommon metadata types need a separately reviewed full release;
    # silently dropping them would make an apparently identical image unsafe.
    if config.get("Volumes") or config.get("OnBuild") or config.get("Healthcheck") or config.get("ArgsEscaped"):
        raise ValueError("Flattening requires a full release review for this image configuration")
    lines = ["FROM scratch", "COPY --from=patched / /"]
    for entry in config.get("Env", []):
        key, value = entry.split("=", 1)
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ValueError("Unsupported image environment key")
        lines.append("ENV " + key + "=" + docker_value(value))
    for key, value in sorted((config.get("Labels") or {}).items()):
        lines.append("LABEL " + docker_value(key) + "=" + docker_value(value))
    for key, instruction in (("WorkingDir", "WORKDIR"), ("User", "USER"), ("StopSignal", "STOPSIGNAL")):
        value = config.get(key)
        if value:
            if not re.fullmatch(r"[A-Za-z0-9_/:.-]+", value):
                raise ValueError("Unsupported image " + key)
            lines.append(instruction + " " + value)
    for port in sorted(config.get("ExposedPorts") or {}):
        if not re.fullmatch(r"\d+/(tcp|udp|sctp)", port):
            raise ValueError("Unsupported image port")
        lines.append("EXPOSE " + port)
    for key, instruction in (("Shell", "SHELL"), ("Entrypoint", "ENTRYPOINT"), ("Cmd", "CMD")):
        if config.get(key) is not None:
            if not isinstance(config[key], list) or not all(isinstance(s, str) for s in config[key]):
                raise ValueError("Unsupported image command metadata")
            lines.append(instruction + " " + json.dumps(config[key]))
    return "\n".join(lines) + "\n"
