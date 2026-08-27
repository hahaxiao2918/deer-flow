"""Regression coverage for local and Docker Gateway startup contracts."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def _deploy_fixture(tmp_path: Path, *, docker_script: str) -> tuple[Path, dict[str, str]]:
    worktree = tmp_path / "repo"
    shutil.copytree(REPO_ROOT / "scripts", worktree / "scripts")
    shutil.copytree(REPO_ROOT / "docker", worktree / "docker")
    (worktree / "backend").mkdir()
    (worktree / "config.yaml").write_text("sandbox:\n  use: deerflow.sandbox:LocalSandboxProvider\n", encoding="utf-8")
    (worktree / "extensions_config.json").write_text('{"mcpServers":{},"skills":{}}\n', encoding="utf-8")
    # Distribution deploy.sh owns the .env file and refuses to run without it
    # (production-deployment safety); the fixture must provide a minimal one.
    (worktree / ".env").write_text("DEER_FLOW_HOME=/tmp/deer-flow-test\n", encoding="utf-8")
    # Distribution deploy.sh also runs config-upgrade against config.example.yaml
    # before composing; the fixture needs the template for that preflight.
    shutil.copy(REPO_ROOT / "config.example.yaml", worktree / "config.example.yaml")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text(docker_script, encoding="utf-8")
    docker.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["BETTER_AUTH_SECRET"] = "test-better-auth-secret"
    env["DEER_FLOW_INTERNAL_AUTH_TOKEN"] = "test-internal-auth-token"
    return worktree, env


def test_gateway_runtime_commands_never_sync_dependencies() -> None:
    """A built environment must not resolve or install packages at process start."""
    compose = _read("docker/docker-compose.yaml")
    serve = _read("scripts/serve.sh")

    assert "PYTHONPATH=. uv run --no-sync uvicorn app.gateway.app:app" in compose
    assert "PYTHONPATH=. uv run --no-sync uvicorn app.gateway.app:app" in serve


def test_local_frontend_ignores_public_docker_port() -> None:
    """Root PORT config is public Docker ingress, not the local Next.js port."""
    serve = _read("scripts/serve.sh")

    assert 'run_service "Frontend"' in serve
    # Distribution: the local dev frontend runs on the high FRONTEND_PORT
    # (default 13000, see the local setup note), passed explicitly to Next.js
    # and never derived from the root PORT (public Docker ingress).
    assert 'FRONTEND_PORT="${FRONTEND_PORT:-13000}"' in serve
    assert "PORT=$FRONTEND_PORT" in serve


def test_production_gateway_has_a_real_readiness_probe() -> None:
    """Compose readiness must exercise the Gateway HTTP endpoint."""
    compose = _read("docker/docker-compose.yaml")

    assert "healthcheck:" in compose
    assert "http://127.0.0.1:8001/health" in compose
    assert "gateway:\n        condition: service_healthy" in compose


def test_deploy_waits_for_gateway_readiness_before_success(tmp_path: Path) -> None:
    capture = tmp_path / "docker-args.txt"
    # Distribution deploy.sh verifies the gateway's bind mounts via
    # `docker inspect` after `up --wait`; the fake docker answers those two
    # queries (Source/Type) with the fixture paths and records everything else.
    worktree, env = _deploy_fixture(
        tmp_path,
        docker_script=(
            "#!/usr/bin/env sh\n"
            'printf "%s\\n" "$@" >> "$CAPTURE_DOCKER_ARGS"\n'
            'case " $* " in\n'
            '  *" inspect "*)\n'
            '    case " $* " in\n'
            '      *".Source"*)\n'
            '        case " $* " in\n'
            '          *"extensions_config.json"*) printf "%s\\n" "$FIXTURE_REPO/extensions_config.json" ;;\n'
            '          *) printf "%s\\n" "$FIXTURE_REPO/config.yaml" ;;\n'
            "        esac ;;\n"
            '      *".Type"*) printf "bind\\n" ;;\n'
            "    esac ;;\n"
            "esac\n"
            "exit 0\n"
        ),
    )
    env["CAPTURE_DOCKER_ARGS"] = str(capture)
    env["FIXTURE_REPO"] = os.path.realpath(worktree)

    result = subprocess.run(
        ["bash", str(worktree / "scripts" / "deploy.sh"), "start"],
        cwd=worktree,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    args = capture.read_text(encoding="utf-8").splitlines()
    assert "--wait" in args
    assert "--wait-timeout" in args
    assert "DeerFlow is running!" in result.stdout


def test_deploy_failure_prints_gateway_diagnostics_and_never_claims_success(tmp_path: Path) -> None:
    capture = tmp_path / "docker-calls.txt"
    worktree, env = _deploy_fixture(
        tmp_path,
        docker_script=('#!/usr/bin/env sh\nprintf "%s\\n" "$*" >> "$CAPTURE_DOCKER_CALLS"\ncase " $* " in\n  *" up "*) exit 1 ;;\n  *) exit 0 ;;\nesac\n'),
    )
    env["CAPTURE_DOCKER_CALLS"] = str(capture)

    result = subprocess.run(
        ["bash", str(worktree / "scripts" / "deploy.sh"), "start"],
        cwd=worktree,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "DeerFlow is running!" not in result.stdout
    assert "DeerFlow services failed to become ready" in result.stderr
    assert "supports `docker compose up --wait`" in result.stderr
    calls = capture.read_text(encoding="utf-8")
    assert any(call.endswith(" ps") for call in calls.splitlines())
    assert " logs --no-color --tail 100 gateway" in calls


def test_deploy_down_survives_missing_or_broken_config(tmp_path: Path) -> None:
    """`deploy.sh down` is the only supported shutdown path, so it must not run
    startup preflights (existence, YAML validation, config-upgrade) that would
    exit 1 or rewrite config.yaml exactly when the config is the broken thing."""
    for scenario, config_text in (
        ("missing", None),
        ("invalid-yaml", "{not: valid: yaml\n"),
    ):
        capture = tmp_path / f"docker-{scenario}.txt"
        worktree, env = _deploy_fixture(
            tmp_path / scenario,
            docker_script=('#!/usr/bin/env sh\nprintf "%s\\n" "$*" >> "$CAPTURE_DOCKER_ARGS"\nexit 0\n'),
        )
        env["CAPTURE_DOCKER_ARGS"] = str(capture)
        if config_text is None:
            (worktree / "config.yaml").unlink()
        else:
            (worktree / "config.yaml").write_text(config_text, encoding="utf-8")

        result = subprocess.run(
            ["bash", str(worktree / "scripts" / "deploy.sh"), "down"],
            cwd=worktree,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, (scenario, result.stderr)
        calls = capture.read_text(encoding="utf-8").splitlines()
        assert any(call.endswith(" down") for call in calls), scenario
        # The config-upgrade preflight must not have run for down.
        assert "Config preflight" not in result.stdout, scenario
