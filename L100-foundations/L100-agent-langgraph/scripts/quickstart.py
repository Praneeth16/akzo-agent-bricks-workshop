#!/usr/bin/env python3
"""Quickstart setup for the L100 LangGraph agent.

NOTE: Keep this comment up to date when editing the script.

Steps:
  1. Check prerequisites — uv, Node.js (>=20.19/22.12/23 for the chat UI), npm,
     Databricks CLI. Exit if any are missing or the Node version is unsupported by Vite.
  2. Set up .env — copy .env.example -> .env (or create a minimal one).
  3. Databricks auth — use --profile if given, else list existing profiles for interactive
     selection, or create a new DEFAULT profile with --host / prompt. Validate; authenticate
     via OAuth if invalid. Save the profile and tracking URI to .env.
  4. MLflow experiment — get the username, reuse MLFLOW_EXPERIMENT_ID from .env if it still
     exists, otherwise create one. Write the ID into .env and databricks.yml.
  5. Print a summary with a link to the experiment.

This agent has NO Lakebase dependency, so there is no Lakebase setup here. The catalog and
LLM endpoint stay portable: they default to current_catalog() and a Foundation Model, and
can be overridden via AKZO_CATALOG / LLM_ENDPOINT in .env (see agent_server/utils.py).

Usage:
    uv run quickstart [OPTIONS]

Options:
    --profile NAME    Use specified Databricks profile (non-interactive)
    --host URL        Databricks workspace URL (for initial setup)
    -h, --help        Show this help message
"""

import argparse
import json
import platform
import re
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import DoubleQuotedScalarString


def _load_yml(path: Path):
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(sequence=4, offset=2)
    with open(path) as f:
        return yaml, yaml.load(f)


def _save_yml(yaml: YAML, data, path: Path) -> None:
    with open(path, "w") as f:
        yaml.dump(data, f)


def print_header(text: str) -> None:
    print(f"\n{'=' * 67}")
    print(text)
    print("=" * 67)


def print_step(text: str) -> None:
    print(f"\n{text}")


def print_success(text: str) -> None:
    print(f"✓ {text}")


def print_error(text: str) -> None:
    print(f"✗ {text}", file=sys.stderr)


def command_exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def run_command(cmd, check=True, env=None):
    import os

    merged_env = {**os.environ, **(env or {})}
    return subprocess.run(cmd, capture_output=True, text=True, check=check, env=merged_env)


def get_command_output(cmd) -> str:
    return run_command(cmd).stdout.strip()


def check_prerequisites() -> dict:
    print_step("Checking prerequisites...")
    prereqs = {
        "uv": command_exists("uv"),
        "node": command_exists("node"),
        "npm": command_exists("npm"),
        "databricks": command_exists("databricks"),
    }
    for name, installed in prereqs.items():
        if installed:
            try:
                version = get_command_output([name, "--version"])
                print_success(f"{name} is installed: {version}")
            except Exception:
                print_success(f"{name} is installed")
        else:
            print(f"  {name} is not installed")
    return prereqs


def check_missing_prerequisites(prereqs: dict) -> list:
    missing = []
    if not prereqs["uv"]:
        missing.append("uv - Install with: curl -LsSf https://astral.sh/uv/install.sh | sh")
    if not prereqs["node"] or not prereqs["npm"]:
        missing.append("Node.js 20 - Install with: nvm install 20 (or download from nodejs.org)")
    if not prereqs["databricks"]:
        if platform.system() == "Darwin":
            missing.append("Databricks CLI - Install with: brew install databricks/tap/databricks")
        else:
            missing.append(
                "Databricks CLI - Install with: curl -fsSL "
                "https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh"
            )
    return missing


def check_node_version() -> str | None:
    """Vite requires Node >=20.19, >=22.12, or >=23. Node 21.x is unsupported."""
    if not command_exists("node"):
        return None
    try:
        version_str = get_command_output(["node", "--version"])
    except Exception:
        return None
    match = re.match(r"v(\d+)\.(\d+)\.(\d+)", version_str)
    if not match:
        return None
    major, minor = int(match.group(1)), int(match.group(2))
    if major == 21:
        return f"Node.js {version_str} is not supported by Vite. Run: nvm install 22"
    if (major == 20 and minor >= 19) or (major == 22 and minor >= 12) or major >= 23:
        return None
    return f"Node.js {version_str} is too old for Vite (needs 20.19+/22.12+/23+). Run: nvm install 22"


def setup_env_file() -> None:
    print_step("Setting up configuration files...")
    env_local = Path(".env")
    env_example = Path(".env.example")
    if env_local.exists():
        print("  .env already exists, skipping copy...")
    elif env_example.exists():
        shutil.copy(env_example, env_local)
        print_success("Copied .env.example to .env")
    else:
        env_local.write_text(
            "DATABRICKS_CONFIG_PROFILE=DEFAULT\n"
            "MLFLOW_EXPERIMENT_ID=\n"
            'MLFLOW_TRACKING_URI="databricks"\n'
            'MLFLOW_REGISTRY_URI="databricks-uc"\n'
        )
        print_success("Created .env")


def update_env_file(key: str, value: str) -> None:
    env_file = Path(".env")
    if not env_file.exists():
        env_file.write_text(f"{key}={value}\n")
        return
    content = env_file.read_text()
    active = rf"^{re.escape(key)}=.*$"
    if re.search(active, content, re.MULTILINE):
        content = re.sub(active, f"{key}={value}", content, flags=re.MULTILINE)
    else:
        if not content.endswith("\n"):
            content += "\n"
        content += f"{key}={value}\n"
    env_file.write_text(content)


def get_env_value(key: str) -> str:
    env_file = Path(".env")
    if not env_file.exists():
        return ""
    match = re.search(rf"^{re.escape(key)}=(.*)$", env_file.read_text(), re.MULTILINE)
    return match.group(1).strip().strip('"').strip("'") if match else ""


def get_databricks_profiles() -> list:
    try:
        result = run_command(["databricks", "auth", "profiles"], check=False)
        if result.returncode != 0 or not result.stdout.strip():
            return []
        lines = result.stdout.strip().split("\n")
        return [
            {"name": line.split()[0], "line": line}
            for line in lines[1:]
            if line.strip() and line.split()
        ]
    except Exception:
        return []


def validate_profile(profile_name: str) -> bool:
    try:
        result = run_command(
            ["databricks", "current-user", "me"],
            check=False,
            env={"DATABRICKS_CONFIG_PROFILE": profile_name},
        )
        return result.returncode == 0
    except Exception:
        return False


def authenticate_profile(profile_name: str, host: str = None) -> bool:
    print(f"\nAuthenticating profile '{profile_name}' (a browser window will open)...\n")
    cmd = ["databricks", "auth", "login", "--profile", profile_name]
    if host:
        cmd.extend(["--host", host])
    try:
        return subprocess.run(cmd).returncode == 0
    except Exception as e:
        print_error(f"Authentication failed: {e}")
        return False


def select_profile_interactive(profiles: list) -> str:
    print("\nFound existing Databricks profiles:\n")
    for i, profile in enumerate(profiles, 1):
        print(f"  {i}) {profile['line']}")
    print()
    while True:
        choice = input("Enter the number of the profile you want to use: ").strip()
        try:
            index = int(choice) - 1
            if 0 <= index < len(profiles):
                return profiles[index]["name"]
        except ValueError:
            pass
        print_error(f"Please enter a number between 1 and {len(profiles)}")


def setup_databricks_auth(profile_arg=None, host_arg=None) -> str:
    print_step("Setting up Databricks authentication...")
    if profile_arg:
        profile_name = profile_arg
        print(f"Using specified profile: {profile_name}")
    else:
        profiles = get_databricks_profiles()
        profile_name = select_profile_interactive(profiles) if profiles else None

    if profile_name:
        if validate_profile(profile_name):
            print_success(f"Validated profile '{profile_name}'")
        else:
            print(f"Profile '{profile_name}' is not authenticated.")
            if not authenticate_profile(profile_name):
                print_error(f"Failed to authenticate profile '{profile_name}'")
                sys.exit(1)
    else:
        host = host_arg or input(
            "\nEnter your Databricks host URL "
            "(e.g. https://your-workspace.cloud.databricks.com): "
        ).strip()
        if not host:
            print_error("Databricks host is required")
            sys.exit(1)
        profile_name = "DEFAULT"
        if not authenticate_profile(profile_name, host):
            print_error("Databricks authentication failed")
            sys.exit(1)

    update_env_file("DATABRICKS_CONFIG_PROFILE", profile_name)
    update_env_file("MLFLOW_TRACKING_URI", f'"databricks://{profile_name}"')
    print_success(f"Databricks profile '{profile_name}' saved to .env")
    return profile_name


def get_workspace_client(profile_name: str):
    try:
        from databricks.sdk import WorkspaceClient

        return WorkspaceClient(profile=profile_name)
    except Exception:
        return None


def get_databricks_host(profile_name: str) -> str:
    try:
        result = run_command(
            ["databricks", "auth", "env", "--profile", profile_name, "--output", "json"],
            check=False,
        )
        if result.returncode == 0:
            return json.loads(result.stdout).get("env", {}).get("DATABRICKS_HOST", "").rstrip("/")
    except Exception:
        pass
    return ""


def get_databricks_username(profile_name: str) -> str:
    w = get_workspace_client(profile_name)
    if not w:
        print_error("Could not connect to Databricks workspace")
        sys.exit(1)
    try:
        return w.current_user.me().user_name or ""
    except Exception as e:
        print_error(f"Failed to get Databricks username: {e}")
        sys.exit(1)


def create_mlflow_experiment(profile_name: str, username: str):
    print_step("Setting up MLflow experiment...")
    w = get_workspace_client(profile_name)
    if not w:
        print_error("Could not connect to Databricks workspace")
        sys.exit(1)

    existing_id = get_env_value("MLFLOW_EXPERIMENT_ID")
    if existing_id:
        try:
            exp = w.experiments.get_experiment(experiment_id=existing_id).experiment
            if exp and exp.name:
                print_success(f"Reusing experiment '{exp.name}' (ID: {existing_id})")
                return exp.name, existing_id
        except Exception:
            print("Existing experiment not found, creating a new one...")

    name = f"/Users/{username}/akzo-l100-langgraph-agent"
    try:
        try:
            exp_id = w.experiments.create_experiment(name=name).experiment_id or ""
            print_success(f"Created experiment '{name}' (ID: {exp_id})")
            return name, exp_id
        except Exception:
            name = f"{name}-{secrets.token_hex(4)}"
            exp_id = w.experiments.create_experiment(name=name).experiment_id or ""
            print_success(f"Created experiment '{name}' (ID: {exp_id})")
            return name, exp_id
    except Exception as e:
        print_error(f"Failed to create MLflow experiment: {e}")
        sys.exit(1)


def update_databricks_yml_experiment(experiment_id: str) -> None:
    yml_path = Path("databricks.yml")
    if not yml_path.exists():
        return
    yaml, data = _load_yml(yml_path)
    apps = data.get("resources", {}).get("apps", {})
    for app_val in apps.values():
        for resource in app_val.get("resources", []):
            if "experiment" in resource:
                resource["experiment"]["experiment_id"] = DoubleQuotedScalarString(experiment_id)
    _save_yml(yaml, data, yml_path)
    print_success("Updated databricks.yml with experiment ID")


def main():
    parser = argparse.ArgumentParser(
        description="Quickstart setup for the L100 LangGraph agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    uv run quickstart                     # Interactive setup
    uv run quickstart --profile DEFAULT   # Use existing profile (non-interactive)
    uv run quickstart --host https://...  # Set up a new profile with a host
        """,
    )
    parser.add_argument("--profile", metavar="NAME", help="Databricks profile (non-interactive)")
    parser.add_argument("--host", metavar="URL", help="Databricks workspace URL (initial setup)")
    args = parser.parse_args()

    try:
        print_header("AkzoNobel L100 LangGraph Agent - Quickstart Setup")

        prereqs = check_prerequisites()
        missing = check_missing_prerequisites(prereqs)
        if missing:
            print_step("Missing prerequisites:")
            for item in missing:
                print(f"  • {item}")
            sys.exit(1)

        node_error = check_node_version()
        if node_error:
            print_error(f"Node.js version check failed:\n  {node_error}")
            sys.exit(1)

        setup_env_file()
        profile_name = setup_databricks_auth(args.profile, args.host)

        print_step("Getting Databricks username...")
        username = get_databricks_username(profile_name)
        print(f"Username: {username}")

        experiment_name, experiment_id = create_mlflow_experiment(profile_name, username)
        update_env_file("MLFLOW_EXPERIMENT_ID", experiment_id)
        print_success("Updated .env with experiment ID")
        update_databricks_yml_experiment(experiment_id)

        host = get_databricks_host(profile_name)
        print_header("Setup Complete!")
        summary = (
            f"\n✓ Databricks authenticated with profile: {profile_name}"
            f"\n✓ Configuration written to .env"
            f"\n✓ MLflow experiment: {experiment_name} (ID: {experiment_id})"
        )
        if host and experiment_id:
            summary += f"\n  {host}/ml/experiments/{experiment_id}"
        summary += (
            "\n\nThe catalog defaults to current_catalog() and the LLM to a Foundation Model."
            "\nOverride them with AKZO_CATALOG / LLM_ENDPOINT in .env if your data lives elsewhere."
            "\n\nNext step: run 'uv run start-app' to start the agent locally.\n"
        )
        print(summary)

    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
        sys.exit(1)


if __name__ == "__main__":
    main()
