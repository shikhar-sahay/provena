# Provena local development helper (Windows PowerShell).
#
# Usage from the repository root:
#   ./scripts/dev.ps1 setup        full first-time setup (db, venv, deps, migrate, seed)
#   ./scripts/dev.ps1 api          run the backend API with reload
#   ./scripts/dev.ps1 web          run the frontend dev server
#   ./scripts/dev.ps1 demo         seed the synthetic demo investigation
#   ./scripts/dev.ps1 health       check db, api health, and ports
#   ./scripts/dev.ps1 reset -Force wipe the dev database and reseed from scratch
#
# Native path: Docker Postgres on host :5433, backend and frontend from source.
# Full-container path: docker compose up --build (see docs/development.md).

param(
    [Parameter(Position = 0)]
    [ValidateSet("setup", "api", "web", "demo", "health", "reset")]
    [string]$Task = "setup",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"
$DbUrl = "postgresql+psycopg2://provena:provena@localhost:5433/provena"

function Step($message) { Write-Host "==> $message" }

function Require-Command($name) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "Required command '$name' was not found on PATH."
    }
}

function Invoke-Compose([string[]]$composeArgs) {
    Push-Location $Root
    try {
        & docker compose @composeArgs
        if ($LASTEXITCODE -ne 0) {
            throw "docker compose $($composeArgs -join ' ') failed with exit code $LASTEXITCODE."
        }
    } finally {
        Pop-Location
    }
}

function Wait-ForPostgres {
    Step "Waiting for PostgreSQL on localhost:5433"
    for ($attempt = 1; $attempt -le 20; $attempt++) {
        try {
            $client = New-Object Net.Sockets.TcpClient
            $async = $client.BeginConnect("127.0.0.1", 5433, $null, $null)
            if ($async.AsyncWaitHandle.WaitOne(1000) -and $client.Connected) {
                $client.Close()
                Write-Host "PostgreSQL is accepting connections."
                return
            }
            $client.Close()
        } catch {
            # Retry below.
        }
        Start-Sleep -Seconds 3
    }
    throw "PostgreSQL did not accept connections on localhost:5433. Is Docker Desktop running with the db service up? Check with: docker compose ps db"
}

function Ensure-Db {
    Step "Starting Provena PostgreSQL (host :5433)"
    Invoke-Compose @("up", "-d", "db")
    Wait-ForPostgres
}

function Ensure-Venv {
    if (-not (Test-Path $VenvPython)) {
        Step "Creating backend virtual environment"
        & python -m venv (Join-Path $Backend ".venv")
        if ($LASTEXITCODE -ne 0) {
            throw "Creating the virtual environment failed with exit code $LASTEXITCODE."
        }
    }
    Step "Installing backend dependencies"
    & $VenvPython -m pip install -q -r (Join-Path $Backend "requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "Installing backend dependencies failed with exit code $LASTEXITCODE."
    }
}

function Backend-Env {
    # Native backend runs resolve DATABASE_URL from the process environment.
    # backend/.env is the persistent local fallback; created once, never overwritten.
    $envFile = Join-Path $Backend ".env"
    if (-not (Test-Path $envFile)) {
        Step "Writing backend/.env with local development defaults"
        @"
DATABASE_URL=$DbUrl
CORS_ORIGINS=http://localhost:5173
"@ | Set-Content -LiteralPath $envFile
    }
}

function Invoke-Backend($scriptArgs) {
    $previous = $env:DATABASE_URL
    $env:DATABASE_URL = $DbUrl
    try {
        Push-Location $Backend
        try {
            & $VenvPython @scriptArgs
            if ($LASTEXITCODE -ne 0) {
                throw "Backend command ($($scriptArgs -join ' ')) failed with exit code $LASTEXITCODE."
            }
        } finally {
            Pop-Location
        }
    } finally {
        $env:DATABASE_URL = $previous
    }
}

switch ($Task) {
    "setup" {
        Require-Command "docker"
        Require-Command "python"
        Require-Command "node"
        Ensure-Db
        Ensure-Venv
        Backend-Env
        Step "Applying migrations"
        Invoke-Backend @("-m", "alembic", "upgrade", "head")
        Step "Seeding development users"
        Invoke-Backend @("-m", "app.seed")
        Write-Host ""
        Write-Host "Setup complete. Next steps:"
        Write-Host "  ./scripts/dev.ps1 demo   (optional synthetic investigation)"
        Write-Host "  ./scripts/dev.ps1 api    (backend on :8000, new terminal)"
        Write-Host "  ./scripts/dev.ps1 web    (frontend on :5173, new terminal)"
    }
    "api" {
        if (-not (Test-Path $VenvPython)) { throw "Run ./scripts/dev.ps1 setup first." }
        Step "Starting backend API on :8000"
        Invoke-Backend @("-m", "uvicorn", "app.main:app", "--reload", "--port", "8000")
    }
    "web" {
        Step "Starting frontend dev server on :5173"
        Push-Location $Frontend
        try {
            if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
                Step "Installing frontend dependencies"
                & npm install
            }
            & npm run dev
        } finally {
            Pop-Location
        }
    }
    "demo" {
        if (-not (Test-Path $VenvPython)) { throw "Run ./scripts/dev.ps1 setup first." }
        Step "Seeding synthetic demo investigation"
        Invoke-Backend @("-m", "app.seed_demo")
    }
    "health" {
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 5
            Write-Host ("API: " + ($health | ConvertTo-Json -Compress))
        } catch {
            Write-Host "API: not reachable on :8000 (start it with ./scripts/dev.ps1 api)"
        }
        Invoke-Compose @("ps", "db") 2>$null | Select-Object -Last 2
    }
    "reset" {
        if (-not $Force) {
            throw "reset wipes the dev database. Re-run with -Force to confirm."
        }
        Step "Wiping dev database volume and reseeding"
        Invoke-Compose @("down", "-v")
        Ensure-Db
        Ensure-Venv
        Backend-Env
        Invoke-Backend @("-m", "alembic", "upgrade", "head")
        Invoke-Backend @("-m", "app.seed")
        Write-Host "Reset complete."
    }
}
