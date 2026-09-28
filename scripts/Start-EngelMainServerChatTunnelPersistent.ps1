param(
    [string]$CtHost = "192.0.2.50",
    [int]$CtPort = 24622,
    [string]$CtUser = "root",
    [string]$KeyPath = (Join-Path $env:USERPROFILE ".ssh\engel_ai_main_ct246_ed25519"),
    [string]$LocalBind = "127.0.0.1",
    [int]$ChatLocalPort = 24680,
    [int]$ChatRemotePort = 8765,
    # Chat is only on 24680 by default. Do NOT alias loopback 8765 to CT chat —
    # that steals 127.0.0.1:8765 from Android USB adb-reverse pairing (lan-receiver).
    # Set -ChatAliasLocalPort 8765 only for temporary CT-debug if phones are not using reverse.
    [int]$ChatAliasLocalPort = 0,
    [int]$MeetingLocalPort = 8790,
    [int]$MeetingRemotePort = 8790,
    [int]$OfficeLocalPort = 3000,
    [int]$OfficeRemotePort = 3000,
    [int]$GrokBridgeLocalPort = 24880,
    [int]$GrokBridgeRemotePort = 24881,
    [int]$ClaudeBridgeLocalPort = 24882,
    [int]$ClaudeBridgeRemotePort = 24883,
    [int]$ChatGptBridgeLocalPort = 24884,
    [int]$ChatGptBridgeRemotePort = 24885,
    [int]$GeminiBridgeLocalPort = 24886,
    [int]$GeminiBridgeRemotePort = 24887,
    [int]$CodexBridgeLocalPort = 24888,
    [int]$CodexBridgeRemotePort = 24889,
    [int]$ImagineLocalPort = 24890,
    [int]$ImagineRemotePort = 24890,
    [int]$QueueImportLocalPort = 8765,
    [int]$QueueImportRemotePort = 18765,
    # Queue -R uses the LAN pairing bind (192.0.2.40:8765). Loopback 8765 is for
    # USB adb-reverse pairing, not the CT chat alias. engel-ai-rs queue_import_allowed
    # must accept peer 192.0.2.40 (same-host LAN bind) for this relay to succeed.
    [string]$QueueImportLocalHost = "192.0.2.40",
    [string]$SubEngelHost = "198.51.100.227",
    [int]$SubEngelPort = 8776,
    [int]$SubEngelRemotePort = 18777,
    [int]$ReconnectSeconds = 5,
    [switch]$EnableProviderBridges,
    [switch]$SkipGrokBridge,
    # Default: Claude disconnected from Engel — keep skipped unless operator opts in.
    [switch]$SkipClaudeBridge = $true,
    [switch]$SkipChatGptBridge,
    [switch]$SkipGeminiBridge,
    [switch]$SkipCodexBridge,
    [switch]$SkipQueueImportRelay,
    [switch]$SkipSubEngelRelay,
    [switch]$Once
)

$ErrorActionPreference = "Stop"

function Assert-Port {
    param([int]$Port, [string]$Name)
    if ($Port -lt 1 -or $Port -gt 65535) {
        throw "$Name must be a TCP port from 1 to 65535."
    }
}

function Write-LinkLog {
    param([string]$Message)
    $line = "{0} {1}" -f (Get-Date).ToUniversalTime().ToString("o"), $Message
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $script:LogPath) | Out-Null
    Add-Content -LiteralPath $script:LogPath -Value $line -Encoding UTF8
    Write-Host $line
}

foreach ($item in @(
    @{ Port = $CtPort; Name = "CtPort" },
    @{ Port = $ChatLocalPort; Name = "ChatLocalPort" },
    @{ Port = $ChatRemotePort; Name = "ChatRemotePort" },
    @{ Port = $MeetingLocalPort; Name = "MeetingLocalPort" },
    @{ Port = $MeetingRemotePort; Name = "MeetingRemotePort" },
    @{ Port = $OfficeLocalPort; Name = "OfficeLocalPort" },
    @{ Port = $OfficeRemotePort; Name = "OfficeRemotePort" },
    @{ Port = $GrokBridgeLocalPort; Name = "GrokBridgeLocalPort" },
    @{ Port = $GrokBridgeRemotePort; Name = "GrokBridgeRemotePort" },
    @{ Port = $ClaudeBridgeLocalPort; Name = "ClaudeBridgeLocalPort" },
    @{ Port = $ClaudeBridgeRemotePort; Name = "ClaudeBridgeRemotePort" },
    @{ Port = $ChatGptBridgeLocalPort; Name = "ChatGptBridgeLocalPort" },
    @{ Port = $ChatGptBridgeRemotePort; Name = "ChatGptBridgeRemotePort" },
    @{ Port = $GeminiBridgeLocalPort; Name = "GeminiBridgeLocalPort" },
    @{ Port = $GeminiBridgeRemotePort; Name = "GeminiBridgeRemotePort" },
    @{ Port = $CodexBridgeLocalPort; Name = "CodexBridgeLocalPort" },
    @{ Port = $CodexBridgeRemotePort; Name = "CodexBridgeRemotePort" },
    @{ Port = $QueueImportLocalPort; Name = "QueueImportLocalPort" },
    @{ Port = $QueueImportRemotePort; Name = "QueueImportRemotePort" },
    @{ Port = $SubEngelPort; Name = "SubEngelPort" },
    @{ Port = $SubEngelRemotePort; Name = "SubEngelRemotePort" }
)) {
    Assert-Port -Port $item.Port -Name $item.Name
}
# ChatAliasLocalPort=0 means disabled (keeps 127.0.0.1:8765 free for USB adb reverse pairing).
if ($ChatAliasLocalPort -ne 0) {
    Assert-Port -Port $ChatAliasLocalPort -Name "ChatAliasLocalPort"
}

$ResolvedKeyPath = [System.IO.Path]::GetFullPath($KeyPath)
if (-not (Test-Path -LiteralPath $ResolvedKeyPath -PathType Leaf)) {
    throw "Engel CT SSH key was not found: $ResolvedKeyPath. Run scripts\Install-EngelMainPersistentAgenticSystem.ps1 once."
}

$LogPath = Join-Path $env:LOCALAPPDATA "Engel AI Main\logs\server-link-tunnel.log"
$createdNew = $false
$mutex = New-Object System.Threading.Mutex($true, "Local\EngelMainServerPersistentLink", [ref]$createdNew)
if (-not $createdNew) {
    $expectedForward = "-L ${LocalBind}:${ChatLocalPort}:127.0.0.1:${ChatRemotePort}"
    $expectedGrok = "-R 127.0.0.1:${GrokBridgeRemotePort}:${LocalBind}:${GrokBridgeLocalPort}"
    $liveForward = Get-CimInstance Win32_Process -Filter "Name='ssh.exe'" -ErrorAction SilentlyContinue |
        Where-Object {
            $_.CommandLine -and
            $_.CommandLine.Contains($expectedForward) -and
            $_.CommandLine.Contains($expectedGrok)
        } |
        Select-Object -First 1
    if (-not $liveForward) {
        $staleTunnelProcesses = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
            Where-Object {
                $_.ProcessId -ne $PID -and
                $_.CommandLine -and
                $_.CommandLine.Contains('Start-EngelMainServerChatTunnelPersistent.ps1')
            }
        foreach ($stale in $staleTunnelProcesses) {
            Write-LinkLog "Removing stale persistent-link owner pid=$($stale.ProcessId); no expected SSH forward is alive."
            Stop-Process -Id $stale.ProcessId -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Milliseconds 750
        $mutex.Dispose()
        $createdNew = $false
        $mutex = New-Object System.Threading.Mutex($true, "Local\EngelMainServerPersistentLink", [ref]$createdNew)
    }
    if (-not $createdNew) {
        Write-LinkLog "Persistent Engel server link is already running with its SSH forward; exiting duplicate tunnel process."
        exit 0
    }
}

function Ensure-RogBridges {
    # Idempotent: each bridge launcher exits fast when its service already
    # answers /health. Called on EVERY reconnect iteration (not just once at
    # start) so bridges that died while the tunnel stayed up are revived on the
    # next loop pass - a dead bridge set is what turned chat into canned
    # template replies on 2026-07-01.
    if (-not $EnableProviderBridges) {
        Write-LinkLog "Provider bridge launch skipped by local-first policy. Use -EnableProviderBridges only when a provider fallback is required."
        return
    }

    $imagineScript = Join-Path $PSScriptRoot "Start-EngelGrokImagineService.ps1"
    if (Test-Path -LiteralPath $imagineScript -PathType Leaf) {
        try {
            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $imagineScript | Out-Null
            Write-LinkLog "ROG Grok Imagine service checked at 127.0.0.1:24890."
        } catch {
            Write-LinkLog "ROG Grok Imagine service start/check failed: $($_.Exception.Message)"
        }
    }
    if (-not $SkipGrokBridge) {
        $grokBridgeScript = Join-Path $PSScriptRoot "Start-EngelGrokCliBridge.ps1"
        if (Test-Path -LiteralPath $grokBridgeScript -PathType Leaf) {
            try {
                & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $grokBridgeScript -HostAddress $LocalBind -Port $GrokBridgeLocalPort
                Write-LinkLog "ROG Grok CLI bridge checked at ${LocalBind}:${GrokBridgeLocalPort}."
            } catch {
                Write-LinkLog "ROG Grok CLI bridge start/check failed: $($_.Exception.Message)"
            }
        } else {
            Write-LinkLog "ROG Grok CLI bridge launcher missing: $grokBridgeScript"
        }
    }

    if (-not $SkipClaudeBridge) {
        $claudeBridgeScript = Join-Path $PSScriptRoot "Start-EngelClaudeCliBridge.ps1"
        if (Test-Path -LiteralPath $claudeBridgeScript -PathType Leaf) {
            try {
                & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $claudeBridgeScript -HostAddress $LocalBind -Port $ClaudeBridgeLocalPort
                Write-LinkLog "ROG Claude CLI bridge checked at ${LocalBind}:${ClaudeBridgeLocalPort}."
            } catch {
                Write-LinkLog "ROG Claude CLI bridge start/check failed: $($_.Exception.Message)"
            }
        } else {
            Write-LinkLog "ROG Claude CLI bridge launcher missing: $claudeBridgeScript"
        }
    }

    if (-not $SkipChatGptBridge) {
        $chatGptBridgeScript = Join-Path $PSScriptRoot "Start-EngelChatGptBrowserBridge.ps1"
        if (Test-Path -LiteralPath $chatGptBridgeScript -PathType Leaf) {
            try {
                & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $chatGptBridgeScript -HostAddress $LocalBind -Port $ChatGptBridgeLocalPort
                Write-LinkLog "ROG ChatGPT browser bridge checked at ${LocalBind}:${ChatGptBridgeLocalPort}."
            } catch {
                Write-LinkLog "ROG ChatGPT browser bridge start/check failed: $($_.Exception.Message)"
            }
        } else {
            Write-LinkLog "ROG ChatGPT browser bridge launcher missing: $chatGptBridgeScript"
        }
    }

    if (-not $SkipGeminiBridge) {
        $geminiBridgeScript = Join-Path $PSScriptRoot "Start-EngelGeminiApiBridge.ps1"
        if (Test-Path -LiteralPath $geminiBridgeScript -PathType Leaf) {
            try {
                & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $geminiBridgeScript -HostAddress $LocalBind -Port $GeminiBridgeLocalPort
                Write-LinkLog "ROG Gemini API bridge checked at ${LocalBind}:${GeminiBridgeLocalPort}."
            } catch {
                Write-LinkLog "ROG Gemini API bridge start/check failed: $($_.Exception.Message)"
            }
        } else {
            Write-LinkLog "ROG Gemini API bridge launcher missing: $geminiBridgeScript"
        }
    }

    if (-not $SkipCodexBridge) {
        $codexBridgeScript = Join-Path $PSScriptRoot "Start-EngelCodexCliBridge.ps1"
        if (Test-Path -LiteralPath $codexBridgeScript -PathType Leaf) {
            try {
                & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $codexBridgeScript -HostAddress $LocalBind -Port $CodexBridgeLocalPort
                Write-LinkLog "ROG Codex CLI bridge checked at ${LocalBind}:${CodexBridgeLocalPort}."
            } catch {
                Write-LinkLog "ROG Codex CLI bridge start/check failed: $($_.Exception.Message)"
            }
        } else {
            Write-LinkLog "ROG Codex CLI bridge launcher missing: $codexBridgeScript"
        }
    }
}

try {
    do {
        Ensure-RogBridges
        $sshOk = Test-NetConnection -ComputerName $CtHost -Port $CtPort -InformationLevel Quiet -WarningAction SilentlyContinue
        if (-not $sshOk) {
            Write-LinkLog "CT SSH route unavailable at ${CtHost}:${CtPort}; retrying in ${ReconnectSeconds}s."
            if ($Once) { exit 2 }
            Start-Sleep -Seconds $ReconnectSeconds
            continue
        }

        $sshArgs = @(
            "-i", $ResolvedKeyPath,
            "-N",
            "-o", "BatchMode=yes",
            "-o", "ExitOnForwardFailure=yes",
            "-o", "ServerAliveInterval=30",
            "-o", "ServerAliveCountMax=3",
            "-o", "StrictHostKeyChecking=accept-new",
            "-L", "${LocalBind}:${ChatLocalPort}:127.0.0.1:${ChatRemotePort}",
            "-L", "${LocalBind}:${MeetingLocalPort}:127.0.0.1:${MeetingRemotePort}",
            "-L", "${LocalBind}:${OfficeLocalPort}:127.0.0.1:${OfficeRemotePort}",
            "-R", "127.0.0.1:${GrokBridgeRemotePort}:${LocalBind}:${GrokBridgeLocalPort}",
            "-R", "127.0.0.1:${ClaudeBridgeRemotePort}:${LocalBind}:${ClaudeBridgeLocalPort}",
            "-R", "127.0.0.1:${ChatGptBridgeRemotePort}:${LocalBind}:${ChatGptBridgeLocalPort}",
            "-R", "127.0.0.1:${GeminiBridgeRemotePort}:${LocalBind}:${GeminiBridgeLocalPort}",
            "-R", "127.0.0.1:${CodexBridgeRemotePort}:${LocalBind}:${CodexBridgeLocalPort}",
            # imagine service (ROG-local :24890) -> CT246 :24890 so the CT-side
            # Discord bridge's meme/media fallback can actually reach it
            # (20260711 fix: this forward was missing and the bridge failed silently)
            "-R", "127.0.0.1:${ImagineRemotePort}:${LocalBind}:${ImagineLocalPort}",
            "-p", [string]$CtPort,
            "${CtUser}@${CtHost}"
        )
        if ($ChatAliasLocalPort -gt 0) {
            $insertAt = [Array]::IndexOf($sshArgs, "-L")
            if ($insertAt -lt 0) {
                throw "Internal SSH argument layout error: missing -L before chat alias insert."
            }
            # Insert after the primary chat -L so optional alias stays next to it.
            $aliasArg = @("-L", "${LocalBind}:${ChatAliasLocalPort}:127.0.0.1:${ChatRemotePort}")
            $sshArgs = @($sshArgs[0..($insertAt + 1)] + $aliasArg + $sshArgs[($insertAt + 2)..($sshArgs.Count - 1)])
        }
        if (-not $SkipQueueImportRelay) {
            $insertAt = [Array]::IndexOf($sshArgs, "-p")
            if ($insertAt -lt 0) {
                throw "Internal SSH argument layout error: missing -p before destination."
            }
            $queueRelayArgs = @("-R", "127.0.0.1:${QueueImportRemotePort}:${QueueImportLocalHost}:${QueueImportLocalPort}")
            $sshArgs = @($sshArgs[0..($insertAt - 1)] + $queueRelayArgs + $sshArgs[$insertAt..($sshArgs.Count - 1)])
        }
        if (-not $SkipSubEngelRelay) {
            $insertAt = [Array]::IndexOf($sshArgs, "-p")
            if ($insertAt -lt 0) {
                throw "Internal SSH argument layout error: missing -p before destination."
            }
            $subRelayArgs = @("-R", "127.0.0.1:${SubEngelRemotePort}:${SubEngelHost}:${SubEngelPort}")
            $sshArgs = @($sshArgs[0..($insertAt - 1)] + $subRelayArgs + $sshArgs[$insertAt..($sshArgs.Count - 1)])
        }

        $subRelayLog = if ($SkipSubEngelRelay) { "sub-engel relay skipped" } else { "sub-engel CT:${SubEngelRemotePort}->${SubEngelHost}:${SubEngelPort}" }
        $queueRelayLog = if ($SkipQueueImportRelay) { "assignment queue relay skipped" } else { "assignment queue CT:${QueueImportRemotePort}->ROG:${QueueImportLocalHost}:${QueueImportLocalPort}" }
        Write-LinkLog "Opening ROG persistent link: chat ${LocalBind}:${ChatLocalPort}->CT:${ChatRemotePort}, chat-alias ${LocalBind}:${ChatAliasLocalPort}->CT:${ChatRemotePort}, meeting ${LocalBind}:${MeetingLocalPort}->CT:${MeetingRemotePort}, office ${LocalBind}:${OfficeLocalPort}->CT:${OfficeRemotePort}, grok CT:${GrokBridgeRemotePort}->ROG:${GrokBridgeLocalPort}, claude CT:${ClaudeBridgeRemotePort}->ROG:${ClaudeBridgeLocalPort}, chatgpt CT:${ChatGptBridgeRemotePort}->ROG:${ChatGptBridgeLocalPort}, gemini CT:${GeminiBridgeRemotePort}->ROG:${GeminiBridgeLocalPort}, codex CT:${CodexBridgeRemotePort}->ROG:${CodexBridgeLocalPort}, ${queueRelayLog}, ${subRelayLog}."
        & ssh @sshArgs
        $exitCode = $LASTEXITCODE
        Write-LinkLog "SSH tunnel exited with code ${exitCode}."
        if ($Once) { exit $exitCode }
        Start-Sleep -Seconds $ReconnectSeconds
    } while ($true)
}
finally {
    if ($createdNew) {
        $mutex.ReleaseMutex()
    }
    $mutex.Dispose()
}
