param(
    [string]$CtHost = "192.0.2.50",
    [int]$CtPort = 24622,
    [string]$CtUser = "root",
    [string]$KeyPath = (Join-Path $env:USERPROFILE ".ssh\engel_ai_main_ct246_ed25519"),
    [string]$RuntimeRoot = "/opt/engel",
    [string]$TargetGuildName = "Global Modular",
    [string]$ChannelName = "general",
    [string]$ChannelId = "",
    [switch]$NoTestMessage
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$BridgeScript = Join-Path $ProjectRoot "tools\engel_discord_bridge.py"
$ProfilePath = Join-Path $ProjectRoot "runtime\connector_profiles\channels\discord.json"
$HandoffPath = Join-Path $ProjectRoot "runtime\browser_control\channels\discord.json"
$ResolvedKeyPath = [System.IO.Path]::GetFullPath($KeyPath)

function ConvertFrom-SecureStringPlain {
    param([securestring]$Secure)
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    } finally {
        if ($bstr -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        }
    }
}

function Invoke-DiscordApi {
    param(
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] [string]$Token,
        [string]$Method = "GET",
        [object]$Body = $null
    )
    $uri = "https://discord.com/api/v10$Path"
    $headers = @{ Authorization = "Bot $Token" }
    if ($null -eq $Body) {
        return Invoke-RestMethod -Uri $uri -Method $Method -Headers $headers -TimeoutSec 20
    }
    return Invoke-RestMethod -Uri $uri -Method $Method -Headers $headers -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 8) -TimeoutSec 20
}

function Write-JsonUtf8NoBom {
    param([string]$Path, [object]$Value)
    $dir = Split-Path -Parent $Path
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    $json = $Value | ConvertTo-Json -Depth 12
    $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllText($Path, $json + [Environment]::NewLine, $utf8NoBom)
}

function Write-TextUtf8NoBom {
    param([string]$Path, [string]$Value)
    $dir = Split-Path -Parent $Path
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllText($Path, $Value, $utf8NoBom)
}

if (-not (Test-Path -LiteralPath $ResolvedKeyPath -PathType Leaf)) {
    throw "Missing CT SSH key: $ResolvedKeyPath"
}
if (-not (Test-Path -LiteralPath $BridgeScript -PathType Leaf)) {
    throw "Missing bridge script: $BridgeScript"
}

$savedToken = [Environment]::GetEnvironmentVariable("ENGEL_CONNECTOR_CHANNEL_DISCORD_SECRET", "User")
if ([string]::IsNullOrWhiteSpace($savedToken) -or $savedToken -match '^[0-9a-fA-F]{64}$') {
    Write-Host ""
    Write-Host "Paste the Discord BOT TOKEN from Developer Portal > Engel > Bot > Reset/View Token."
    Write-Host "Do not paste the General Information Public Key. The public key is 64 hex characters and will not bring the bot online."
    Write-Host ""
    $secureToken = Read-Host "Discord Bot token" -AsSecureString
    $botToken = ConvertFrom-SecureStringPlain $secureToken
    if ($null -eq $botToken) {
        $botToken = ""
    } else {
        $botToken = $botToken.Trim()
    }
} else {
    $botToken = $savedToken.Trim()
    Write-Host "Using saved Discord Bot token from Windows user environment."
}
if ([string]::IsNullOrWhiteSpace($botToken)) {
    throw "Discord Bot token was empty."
}
if ($botToken -match '^[0-9a-fA-F]{64}$') {
    throw "That value looks like the Discord Application Public Key, not a Bot token. Open the Bot page and copy/reset the Bot token."
}

Write-Host "Validating Discord bot token..."
try {
    $bot = Invoke-DiscordApi -Path "/users/@me" -Token $botToken
} catch {
    throw "Discord rejected the token. Paste the Bot token from the Bot page, not the public key. $($_.Exception.Message)"
}
if ($bot.bot -ne $true) {
    throw "Discord accepted the credential, but it is not a bot token."
}
Write-Host ("Discord bot verified: {0} ({1})" -f $bot.username, $bot.id)
[Environment]::SetEnvironmentVariable("ENGEL_CONNECTOR_CHANNEL_DISCORD_SECRET", $botToken, "User")
[Environment]::SetEnvironmentVariable("ENGEL_DISCORD_BOT_TOKEN", $botToken, "User")
[Environment]::SetEnvironmentVariable("ENGELCODE_DISCORD_BOT_TOKEN", $botToken, "User")

$guild = $null
try {
    $guilds = Invoke-DiscordApi -Path "/users/@me/guilds" -Token $botToken
    $guild = @($guilds | Where-Object { $_.name -eq $TargetGuildName } | Select-Object -First 1)[0]
    if ($null -eq $guild -and @($guilds).Count -eq 1) {
        $guild = @($guilds)[0]
    }
} catch {
    Write-Host "Guild discovery failed; continuing with supplied ChannelId if present."
}

if ([string]::IsNullOrWhiteSpace($ChannelId)) {
    if ($null -eq $guild) {
        Write-Host "Could not discover target guild '$TargetGuildName'. Installing bridge without a fixed channel id."
        Write-Host "The bridge will answer messages that mention Engel or start with Engel/Hey Engel in visible channels."
    } else {
        try {
            $channels = Invoke-DiscordApi -Path "/guilds/$($guild.id)/channels" -Token $botToken
            $targetChannel = @($channels | Where-Object { $_.type -eq 0 -and $_.name -eq $ChannelName } | Select-Object -First 1)[0]
            if ($null -eq $targetChannel) {
                $targetChannel = @($channels | Where-Object { $_.type -eq 0 } | Select-Object -First 1)[0]
            }
            if ($null -ne $targetChannel) {
                $ChannelId = [string]$targetChannel.id
                $ChannelName = [string]$targetChannel.name
            } else {
                Write-Host "No text channel was visible to the bot in '$($guild.name)'. Installing bridge without a fixed channel id."
            }
        } catch {
            Write-Host "Channel discovery failed; installing bridge without a fixed channel id."
            Write-Host $_.Exception.Message
        }
    }
} else {
    $targetChannel = [pscustomobject]@{ id = $ChannelId; name = $ChannelName }
}

if ($null -ne $guild) {
    $TargetGuildName = [string]$guild.name
}
if ([string]::IsNullOrWhiteSpace($ChannelId)) {
    Write-Host ("Target Discord lane: {0} / visible channels addressed to Engel" -f $TargetGuildName)
} else {
    Write-Host ("Target Discord lane: {0} / #{1} ({2})" -f $TargetGuildName, $ChannelName, $ChannelId)
}
[Environment]::SetEnvironmentVariable("ENGEL_DISCORD_CHANNEL_ID", $ChannelId, "User")
[Environment]::SetEnvironmentVariable("ENGELCODE_DISCORD_CHANNEL_ID", $ChannelId, "User")

$testMessageOk = $false
if (-not $NoTestMessage -and -not [string]::IsNullOrWhiteSpace($ChannelId)) {
    try {
        $null = Invoke-DiscordApi -Path "/channels/$ChannelId/messages" -Method "POST" -Token $botToken -Body @{
            content = "Engel Discord bridge is being activated on CT 246."
        }
        $testMessageOk = $true
        Write-Host "Discord test message posted."
    } catch {
        Write-Host "Discord test message failed. The bot may need Send Messages / View Channel / Read Message History permissions."
        Write-Host $_.Exception.Message
    }
} elseif ([string]::IsNullOrWhiteSpace($ChannelId)) {
    Write-Host "Skipping Discord test message because no fixed channel id is configured."
}

$TempSecretDir = Join-Path $ProjectRoot "runtime\temp\discord_bridge_secret"
New-Item -ItemType Directory -Path $TempSecretDir -Force | Out-Null
$EnvFile = Join-Path $TempSecretDir "discord.env"
$envLines = @(
    "ENGEL_ROOT=$RuntimeRoot",
    "ENGEL_DISCORD_BOT_TOKEN=$botToken",
    "ENGELCODE_DISCORD_BOT_TOKEN=$botToken",
    "ENGEL_DISCORD_CHANNEL_ID=$ChannelId",
    "ENGELCODE_DISCORD_CHANNEL_ID=$ChannelId",
    "ENGEL_DISCORD_CHAT_URL=http://127.0.0.1:8765/chat",
    "ENGEL_DISCORD_REPLY_MODE=mention"
)
Write-TextUtf8NoBom -Path $EnvFile -Value (($envLines -join "`n") + "`n")

try {
    ssh -i $ResolvedKeyPath -p $CtPort -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no "$CtUser@$CtHost" "mkdir -p $RuntimeRoot/tools $RuntimeRoot/run/secrets $RuntimeRoot/logs $RuntimeRoot/run/discord_bridge /etc/systemd/system"
    scp -i $ResolvedKeyPath -P $CtPort -o BatchMode=yes -o StrictHostKeyChecking=no $BridgeScript "$CtUser@$CtHost`:$RuntimeRoot/tools/engel_discord_bridge.py"
    scp -i $ResolvedKeyPath -P $CtPort -o BatchMode=yes -o StrictHostKeyChecking=no $EnvFile "$CtUser@$CtHost`:$RuntimeRoot/run/secrets/discord.env"
    ssh -i $ResolvedKeyPath -p $CtPort -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no "$CtUser@$CtHost" "chmod 700 $RuntimeRoot/run/secrets && chmod 600 $RuntimeRoot/run/secrets/discord.env && chmod +x $RuntimeRoot/tools/engel_discord_bridge.py"
} finally {
    Remove-Item -LiteralPath $EnvFile -Force -ErrorAction SilentlyContinue
}

$remoteSetup = @"
set -euo pipefail
$RuntimeRoot/.venv/bin/python - <<'PY'
import importlib.util, subprocess, sys
missing = [m for m in ("discord", "aiohttp") if importlib.util.find_spec(m) is None]
if missing:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "discord.py", "aiohttp"])
PY
cat > /etc/systemd/system/engel-discord-bridge.service <<'UNIT'
[Unit]
Description=Engel AI Main Discord Bridge
After=network-online.target engel-main-chat.service
Wants=network-online.target engel-main-chat.service

[Service]
Type=simple
WorkingDirectory=$RuntimeRoot
EnvironmentFile=$RuntimeRoot/run/secrets/discord.env
ExecStart=$RuntimeRoot/.venv/bin/python $RuntimeRoot/tools/engel_discord_bridge.py
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now engel-discord-bridge.service
sleep 4
systemctl is-active engel-discord-bridge.service
"@
$tmpRemoteSetup = Join-Path $TempSecretDir "setup_discord_bridge.sh"
Write-TextUtf8NoBom -Path $tmpRemoteSetup -Value ($remoteSetup + "`n")
try {
    scp -i $ResolvedKeyPath -P $CtPort -o BatchMode=yes -o StrictHostKeyChecking=no $tmpRemoteSetup "$CtUser@$CtHost`:/tmp/setup_engel_discord_bridge.sh"
    ssh -i $ResolvedKeyPath -p $CtPort -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no "$CtUser@$CtHost" "bash /tmp/setup_engel_discord_bridge.sh"
} finally {
    Remove-Item -LiteralPath $tmpRemoteSetup -Force -ErrorAction SilentlyContinue
}

$now = [DateTime]::UtcNow.ToString("o")
$profile = if (Test-Path -LiteralPath $ProfilePath) { Get-Content -LiteralPath $ProfilePath -Raw | ConvertFrom-Json } else { [pscustomobject]@{} }
$profile | Add-Member -NotePropertyName schema -NotePropertyValue "engel_connector_profile_v1" -Force
$profile | Add-Member -NotePropertyName connector_kind -NotePropertyValue "channel" -Force
$profile | Add-Member -NotePropertyName connector_id -NotePropertyValue "discord" -Force
$profile | Add-Member -NotePropertyName connector_name -NotePropertyValue "Discord" -Force
$profile | Add-Member -NotePropertyName category -NotePropertyValue "Channels" -Force
$profile | Add-Member -NotePropertyName auth_mode -NotePropertyValue "bot_token" -Force
$profile | Add-Member -NotePropertyName status -NotePropertyValue "discord bridge online from CT 246" -Force
$profile | Add-Member -NotePropertyName application_id -NotePropertyValue "1506157762785312808" -Force
$profile | Add-Member -NotePropertyName application_name -NotePropertyValue "Engel" -Force
$profile | Add-Member -NotePropertyName guild_name -NotePropertyValue $TargetGuildName -Force
$profile | Add-Member -NotePropertyName channel_name -NotePropertyValue $ChannelName -Force
$profile | Add-Member -NotePropertyName channel_id -NotePropertyValue $ChannelId -Force
$profile | Add-Member -NotePropertyName bot_user_id -NotePropertyValue ([string]$bot.id) -Force
$profile | Add-Member -NotePropertyName bot_username -NotePropertyValue ([string]$bot.username) -Force
$profile | Add-Member -NotePropertyName bot_token_valid -NotePropertyValue $true -Force
$profile | Add-Member -NotePropertyName service_name -NotePropertyValue "engel-discord-bridge.service" -Force
$profile | Add-Member -NotePropertyName test_message_posted -NotePropertyValue $testMessageOk -Force
$profile | Add-Member -NotePropertyName updated_at_utc -NotePropertyValue $now -Force
$profile | Add-Member -NotePropertyName secret_policy -NotePropertyValue "Bot token is stored in Windows User environment and CT /opt/engel/run/secrets/discord.env; it is not written to connector profile JSON." -Force
Write-JsonUtf8NoBom -Path $ProfilePath -Value $profile

$handoff = if (Test-Path -LiteralPath $HandoffPath) { Get-Content -LiteralPath $HandoffPath -Raw | ConvertFrom-Json } else { [pscustomobject]@{} }
$handoff | Add-Member -NotePropertyName schema -NotePropertyValue "engel_browser_connector_handoff_v1" -Force
$handoff | Add-Member -NotePropertyName connector_kind -NotePropertyValue "channel" -Force
$handoff | Add-Member -NotePropertyName connector_id -NotePropertyValue "discord" -Force
$handoff | Add-Member -NotePropertyName connector_name -NotePropertyValue "Discord" -Force
$handoff | Add-Member -NotePropertyName auth_mode -NotePropertyValue "bot_token" -Force
$handoff | Add-Member -NotePropertyName status -NotePropertyValue "discord bridge online from CT 246" -Force
$handoff | Add-Member -NotePropertyName updated_at_utc -NotePropertyValue $now -Force
Write-JsonUtf8NoBom -Path $HandoffPath -Value $handoff

scp -i $ResolvedKeyPath -P $CtPort -o BatchMode=yes -o StrictHostKeyChecking=no $ProfilePath "$CtUser@$CtHost`:$RuntimeRoot/runtime/connector_profiles/channels/discord.json" | Out-Null
scp -i $ResolvedKeyPath -P $CtPort -o BatchMode=yes -o StrictHostKeyChecking=no $HandoffPath "$CtUser@$CtHost`:$RuntimeRoot/runtime/browser_control/channels/discord.json" | Out-Null

Write-Host ""
Write-Host "Engel Discord bridge installed and started."
Write-Host ("Service: ssh {0}@{1} -p {2} systemctl status engel-discord-bridge.service" -f $CtUser, $CtHost, $CtPort)
Write-Host ("Discord: {0} / #{1}" -f $TargetGuildName, $ChannelName)
Write-Host "Secrets were not printed."
