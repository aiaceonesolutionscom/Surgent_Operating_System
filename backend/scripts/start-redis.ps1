# Starts Redis inside WSL Ubuntu-24.04.
# Redis auto-starts on WSL boot via systemd (redis-server.service).
# On Linux VPS production, Redis runs natively — this script is Windows-dev only.
#
# NOTE: Python 3.14's async TCP (ProactorEventLoop) cannot reach WSL2's Redis
# from Windows — the rate limiter is designed to fail-open when Redis is
# unreachable, so dev works fine. On the Linux VPS, Redis is localhost-native
# and async connects work perfectly.
$ErrorActionPreference = "SilentlyContinue"

$probe = wsl -d Ubuntu-24.04 -u root bash -c "echo ok" 2>$null
if (-not $probe) {
    Write-Error "WSL distro 'Ubuntu-24.04' not found. Install first: wsl --install -d Ubuntu-24.04"
    exit 1
}

wsl -d Ubuntu-24.04 -u root bash -c "systemctl is-active redis-server >/dev/null 2>&1 && echo running || systemctl start redis-server"

$pong = wsl -d Ubuntu-24.04 -u root bash -c "redis-cli ping"
if ($pong -ne "PONG") {
    Write-Error "Redis failed to start. Run: wsl -d Ubuntu-24.04 -u root systemctl start redis-server"
    exit 1
}

Write-Output "Redis is up on WSL (port 6379). Rate limiter will fail-open on Windows (async limitation)."