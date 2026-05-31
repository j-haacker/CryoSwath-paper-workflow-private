#!/usr/bin/env python3
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import netrc as netrc_mod
import sys
import argparse
from typing import Mapping, Any

try:
    from snakemake.exceptions import WorkflowError
except ModuleNotFoundError:
    WorkflowError = RuntimeError


AUTH_TEST_URL = (
    "https://daacdata.apps.nsidc.org/pub/DATASETS/nsidc0770_rgi_v7/README.txt"
)
NETRC_MACHINE = "urs.earthdata.nasa.gov"


def _log_line(log_path: Path, message: str):
    with open(log_path, "a", encoding="utf-8") as logf:
        logf.write(message.rstrip("\n") + "\n")


def _run_wget(cmd: list[str], log_path: Path) -> bool:
    with open(log_path, "a", encoding="utf-8") as logf:
        proc = subprocess.run(cmd, stdout=logf, stderr=logf, check=False)
    return proc.returncode == 0


def _build_common_download_cmd(tmp_target: Path) -> list[str]:
    return [
        "--keep-session-cookies",
        "--no-check-certificate",
        "--auth-no-challenge=on",
        "-e",
        "robots=off",
        "--no-verbose",
        "--tries=2",
        "--timeout=10",
        "-O",
        str(tmp_target),
        AUTH_TEST_URL,
    ]


def _mktemp_path(prefix: str, suffix: str) -> Path:
    fd, tmp_path = tempfile.mkstemp(prefix=prefix, suffix=suffix)
    os.close(fd)
    return Path(tmp_path)


def _store_cookie(tmp_cookie: Path, cookie_out: Path):
    cookie_out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(tmp_cookie, cookie_out)
    cookie_out.chmod(0o600)


def _netrc_machine_state(netrc_path: Path) -> tuple[bool, str]:
    try:
        parsed = netrc_mod.netrc(str(netrc_path))
    except Exception as exc:  # noqa: BLE001
        return False, f"cannot parse netrc file ({exc})."
    if parsed.authenticators(NETRC_MACHINE) is None:
        return False, f"missing machine '{NETRC_MACHINE}' entry."
    return True, "machine entry present."


def _validate_with_wget_auth(
    auth_args: list[str], cookie_out: Path, log_path: Path
) -> bool:
    tmp_target = _mktemp_path(prefix="nsidc_auth_", suffix=".txt")
    tmp_cookie = _mktemp_path(prefix="nsidc_cookie_", suffix=".txt")
    try:
        cmd = [
            "wget",
            *auth_args,
            "--save-cookies",
            str(tmp_cookie),
            *_build_common_download_cmd(tmp_target),
        ]
        ok = _run_wget(cmd, log_path)
        if ok:
            _store_cookie(tmp_cookie, cookie_out)
        return ok
    finally:
        tmp_target.unlink(missing_ok=True)
        tmp_cookie.unlink(missing_ok=True)


def _as_stripped_nonempty(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _raise_partial_error(source_name: str, user_is_set: bool, pass_is_set: bool):
    missing_parts = []
    if not user_is_set:
        missing_parts.append("username")
    if not pass_is_set:
        missing_parts.append("password")
    key_hint = (
        "`earthdata_username`/`earthdata_password`"
        if source_name == "Config"
        else "`EARTHDATA_USERNAME`/`EARTHDATA_PASSWORD`"
    )
    raise WorkflowError(
        f"{source_name} credentials are partially configured ({key_hint}); missing "
        f"{' and '.join(missing_parts)}."
    )


def _has_interactive_tty() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _run_helper_script_interactively(log_path: Path) -> bool:
    helper_path = Path(__file__).with_name("setup_nsidc_cookies.sh")
    if not helper_path.exists():
        _log_line(log_path, f"helper script missing: {helper_path}")
        return False
    if not _has_interactive_tty():
        _log_line(log_path, "interactive helper skipped (no interactive TTY).")
        return False

    _log_line(log_path, "running interactive helper script once to create cookies.")
    print("No usable NSIDC credentials found. Starting one-time interactive setup.")
    print("Enter credentials once; the workflow will reuse .nsidc_cookies afterwards.")
    proc = subprocess.run(["bash", str(helper_path)], check=False)
    return proc.returncode == 0


def _try_username_password_source(
    source_label: str,
    partial_error_source_name: str,
    username: str,
    password: str,
    output_cookie: Path,
    log_path: Path,
) -> bool:
    user_is_set = bool(username)
    pass_is_set = bool(password)
    if user_is_set != pass_is_set:
        _raise_partial_error(partial_error_source_name, user_is_set, pass_is_set)
    if not user_is_set:
        _log_line(log_path, f"{source_label}: source missing.")
        return False

    _log_line(log_path, f"{source_label}: source found, validating.")
    if _validate_with_wget_auth(
        ["--http-user", username, "--http-password", password],
        output_cookie,
        log_path,
    ):
        _log_line(log_path, f"{source_label}: authentication succeeded.")
        return True
    _log_line(log_path, f"{source_label}: source found but authentication failed.")
    return False


def _try_netrc_source(
    source_label: str,
    netrc_path: Path,
    output_cookie: Path,
    log_path: Path,
    include_path_on_missing: bool = False,
) -> bool:
    if not netrc_path.exists():
        if include_path_on_missing:
            _log_line(log_path, f"{source_label}: source missing ({netrc_path}).")
        else:
            _log_line(log_path, f"{source_label}: source missing.")
        return False
    if not os.access(netrc_path, os.R_OK):
        if include_path_on_missing:
            _log_line(
                log_path,
                f"{source_label}: source missing (not readable: {netrc_path}).",
            )
        else:
            _log_line(log_path, f"{source_label}: source missing (not readable).")
        return False

    _log_line(
        log_path,
        f"{source_label}: source found, validating "
        f"(expects machine '{NETRC_MACHINE}').",
    )
    is_usable, netrc_message = _netrc_machine_state(netrc_path)
    if not is_usable:
        _log_line(
            log_path,
            f"{source_label}: source found but authentication failed ({netrc_message})",
        )
        return False
    if _validate_with_wget_auth(
        ["--netrc-file", str(netrc_path)],
        output_cookie,
        log_path,
    ):
        _log_line(log_path, f"{source_label}: authentication succeeded.")
        return True
    _log_line(log_path, f"{source_label}: source found but authentication failed.")
    return False


def _try_cookie_source(
    source_label: str,
    cookie_in: Path,
    output_cookie: Path,
    log_path: Path,
) -> bool:
    if not cookie_in.exists() or cookie_in.stat().st_size == 0:
        _log_line(log_path, f"{source_label}: source missing.")
        return False

    _log_line(log_path, f"{source_label}: source found, validating.")
    if _validate_with_wget_auth(
        ["--load-cookies", str(cookie_in)],
        output_cookie,
        log_path,
    ):
        _log_line(log_path, f"{source_label}: authentication succeeded.")
        return True
    _log_line(log_path, f"{source_label}: source found but authentication failed.")
    return False


def _resolve_cookie(
    output_cookie: Path,
    log_path: Path,
    config: Mapping[str, Any],
    allow_interactive_helper: bool = True,
):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as logf:
        logf.write("")

    cfg_user = _as_stripped_nonempty(config.get("earthdata_username"))
    cfg_pass = _as_stripped_nonempty(config.get("earthdata_password"))
    if _try_username_password_source(
        source_label="config credentials",
        partial_error_source_name="Config",
        username=cfg_user,
        password=cfg_pass,
        output_cookie=output_cookie,
        log_path=log_path,
    ):
        return

    env_user = _as_stripped_nonempty(os.environ.get("EARTHDATA_USERNAME"))
    env_pass = _as_stripped_nonempty(os.environ.get("EARTHDATA_PASSWORD"))
    if _try_username_password_source(
        source_label="environment credentials",
        partial_error_source_name="Environment",
        username=env_user,
        password=env_pass,
        output_cookie=output_cookie,
        log_path=log_path,
    ):
        return

    home_netrc = Path.home() / ".netrc"
    if _try_netrc_source(
        source_label="$HOME/.netrc",
        netrc_path=home_netrc,
        output_cookie=output_cookie,
        log_path=log_path,
        include_path_on_missing=True,
    ):
        return

    local_netrc = Path(".netrc")
    if _try_netrc_source(
        source_label="./.netrc",
        netrc_path=local_netrc,
        output_cookie=output_cookie,
        log_path=log_path,
    ):
        return

    local_cookie = Path(".nsidc_cookies")
    if _try_cookie_source(
        source_label="./.nsidc_cookies",
        cookie_in=local_cookie,
        output_cookie=output_cookie,
        log_path=log_path,
    ):
        return

    _log_line(log_path, "no credentials found that can authenticate successfully.")
    if allow_interactive_helper and _run_helper_script_interactively(log_path):
        _log_line(log_path, "helper script finished successfully, validating cookie file.")
        if _validate_with_wget_auth(
            ["--load-cookies", str(output_cookie)],
            output_cookie,
            log_path,
        ):
            _log_line(log_path, "interactive helper credentials: authentication succeeded.")
            return
        _log_line(
            log_path,
            "interactive helper credentials: source found but authentication failed.",
        )
    elif not allow_interactive_helper:
        _log_line(log_path, "interactive helper disabled by caller.")

    raise WorkflowError(
        "Could not authenticate with NSIDC Earthdata credentials.\n"
        "Checked in order: "
        "config (earthdata_username/earthdata_password), "
        "environment (EARTHDATA_USERNAME/EARTHDATA_PASSWORD), "
        "$HOME/.netrc, ./.netrc, ./.nsidc_cookies.\n"
        "Snakemake runs this resolver noninteractively. To use a one-time "
        "credential prompt, run it directly outside Snakemake:\n"
        "  python scripts/nsidc_cookies.py\n"
        "If needed, create cookies interactively with:\n"
        "  bash scripts/setup_nsidc_cookies.sh"
    )


def _run_from_snakemake():
    output_cookie = Path(snakemake.output[0])  # noqa: F821
    log_path = Path(snakemake.log[0])  # noqa: F821
    config = snakemake.config  # noqa: F821
    _resolve_cookie(
        output_cookie=output_cookie,
        log_path=log_path,
        config=config,
        allow_interactive_helper=False,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve NSIDC/Earthdata credentials and create .nsidc_cookies."
    )
    parser.add_argument(
        "--output",
        default=".nsidc_cookies",
        help="Cookie output file path (default: .nsidc_cookies).",
    )
    parser.add_argument(
        "--log",
        default="logs/nsidc_cookies.log",
        help="Log file path (default: logs/nsidc_cookies.log).",
    )
    parser.add_argument(
        "--earthdata-username",
        default="",
        help="Optional username to use as highest-priority config source.",
    )
    parser.add_argument(
        "--earthdata-password",
        default="",
        help="Optional password to use as highest-priority config source.",
    )
    parser.add_argument(
        "--no-interactive-helper",
        action="store_true",
        help="Disable automatic one-time interactive helper fallback.",
    )
    return parser.parse_args()


def _run_from_cli():
    args = _parse_args()
    config = {
        "earthdata_username": args.earthdata_username,
        "earthdata_password": args.earthdata_password,
    }
    _resolve_cookie(
        output_cookie=Path(args.output),
        log_path=Path(args.log),
        config=config,
        allow_interactive_helper=not args.no_interactive_helper,
    )
    print(f"Created/updated cookie file: {args.output}")


if "snakemake" in globals():
    _run_from_snakemake()
elif __name__ == "__main__":
    _run_from_cli()
