param(
    [string]$SourceRoot = "",
    [string]$Version = "",
    [string]$OutputRoot = "",
    [switch]$ApprovedGreenGate
)

$ErrorActionPreference = "Stop"

function Get-PortableRelativePath {
    param(
        [Parameter(Mandatory = $true)][string]$BasePath,
        [Parameter(Mandatory = $true)][string]$ChildPath
    )

    $baseFull = [IO.Path]::GetFullPath($BasePath)
    if (-not $baseFull.EndsWith([IO.Path]::DirectorySeparatorChar.ToString(), [StringComparison]::Ordinal)) {
        $baseFull += [IO.Path]::DirectorySeparatorChar
    }
    $childFull = [IO.Path]::GetFullPath($ChildPath)
    if (-not $childFull.StartsWith($baseFull, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Package file escapes the package root: $childFull"
    }
    return $childFull.Substring($baseFull.Length).Replace('\', '/')
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$EngelRoot = [IO.Path]::GetFullPath((Join-Path $ScriptDir ".."))
$WorkspaceRoot = [IO.Path]::GetFullPath((Join-Path $EngelRoot ".."))
$ReleaseParent = [IO.Path]::GetFullPath((Join-Path $EngelRoot "release-staged"))
$MaterialsRoot = Join-Path $EngelRoot "tester-materials\storyboard_movie_creator"
$Verifier = Join-Path $EngelRoot "tools\verify_storyboard_movie_creator_package.py"
$Python = Join-Path $EngelRoot "runtime\python310\python.exe"
$ExpectedProductName = "Engel Storyboard Movie Creator"
$ExpectedCompanyName = "Engel AI Labs"
$ExpectedInternalName = "storyboard_movie_creator"
$ExpectedOriginalFilename = "storyboard_movie_creator.exe"
$ExpectedCopyright = "Copyright (C) 2026 Engel AI Labs. All rights reserved."
$ExpectedWindowTitle = "Engel Storyboard Movie Creator"
$ApprovedIconSha256 = "171e758d1b99b9b09b4d4ad90eac16960ff62c3f4b0403c2c3c4045672dbad5d"
$ApprovedWingedOrbitalMarkSha256 = "0b98aa6dc8334c7242f565558f2ce4313b467bea8ad4a03bdeb4d26ae39df270"
$ApprovedDesktopBackgroundSha256 = "6cb92c93913ca6b7a76b8c625b208588be0dc87254718e45c4e4a4197af51cbe"
$RequiredGates = [ordered]@{
    dart_format = "passed"
    flutter_analyze = "passed"
    flutter_test = "passed"
    flutter_windows_release = "passed"
}

if (-not $ApprovedGreenGate) {
    throw "Packaging is approval-gated. Re-run with -ApprovedGreenGate only after Storyboard source and tests are green."
}

if (-not $SourceRoot) {
    $SourceRoot = "D:\storyboard-movie-creator\StoryboardMovieCreator-StudioRedo-20260822"
}
$SourceRoot = [IO.Path]::GetFullPath($SourceRoot)
$Pubspec = Join-Path $SourceRoot "pubspec.yaml"
if (-not (Test-Path -LiteralPath $Pubspec -PathType Leaf)) {
    throw "Storyboard pubspec.yaml was not found below the selected source root."
}

$versionLine = Select-String -LiteralPath $Pubspec -Pattern '^version:\s*(\S+)\s*$' | Select-Object -First 1
if (-not $versionLine) {
    throw "pubspec.yaml does not contain a readable version field."
}
$PubspecVersion = $versionLine.Matches[0].Groups[1].Value
if (-not $Version) {
    $Version = $PubspecVersion
}
elseif (-not [String]::Equals($Version, $PubspecVersion, [StringComparison]::Ordinal)) {
    throw "Requested version '$Version' does not exactly match pubspec.yaml version '$PubspecVersion'."
}
if ($Version -notmatch '^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$') {
    throw "Version is not a supported pubspec semantic version."
}
$VersionSlug = $Version -replace '[^0-9A-Za-z._-]', '_'

if (-not $OutputRoot) {
    $OutputRoot = Join-Path $ReleaseParent "storyboard-movie-creator-$VersionSlug"
}
$ReleaseRoot = [IO.Path]::GetFullPath($OutputRoot)
$releasePrefix = $ReleaseParent.TrimEnd('\') + '\'
if (-not $ReleaseRoot.StartsWith($releasePrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "OutputRoot must stay below $ReleaseParent"
}

$flutterCandidates = @(
    (Join-Path $WorkspaceRoot "flutter_windows_3.41.9-stable\flutter\bin\flutter.bat"),
    (Join-Path $WorkspaceRoot "flutter_local_sdk\flutter\bin\flutter.bat")
)
$Flutter = $flutterCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if (-not $Flutter) {
    $flutterCommand = Get-Command flutter -ErrorAction SilentlyContinue
    if ($flutterCommand) { $Flutter = $flutterCommand.Source }
}
if (-not $Flutter) {
    throw "A Flutter SDK was not found."
}
$FlutterRoot = [IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $Flutter) ".."))
$Dart = Join-Path $FlutterRoot "bin\cache\dart-sdk\bin\dart.exe"
if (-not (Test-Path -LiteralPath $Dart -PathType Leaf)) {
    throw "The Flutter SDK does not contain its Dart executable."
}
foreach ($required in @($MaterialsRoot, $Verifier, $Python)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required packaging input is missing: $required"
    }
}

$SourceIcon = Join-Path $SourceRoot "windows\runner\resources\app_icon.ico"
$SourceWingedOrbitalMark = Join-Path $SourceRoot "assets\branding\engel-winged-orbital-mark.png"
$SourceDesktopBackground = Join-Path $SourceRoot "assets\branding\engel-desktop-bg.png"
$RunnerResource = Join-Path $SourceRoot "windows\runner\Runner.rc"
$RunnerMain = Join-Path $SourceRoot "windows\runner\main.cpp"
foreach ($required in @($SourceIcon, $SourceWingedOrbitalMark, $SourceDesktopBackground, $RunnerResource, $RunnerMain)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required Storyboard branding input is missing: $required"
    }
}

$sourceIconHash = (Get-FileHash -LiteralPath $SourceIcon -Algorithm SHA256).Hash.ToLowerInvariant()
if (-not [String]::Equals($sourceIconHash, $ApprovedIconSha256, [StringComparison]::Ordinal)) {
    throw "Storyboard app icon is not the approved Engel icon. Expected SHA-256 $ApprovedIconSha256; got $sourceIconHash."
}
$sourceWingedOrbitalMarkHash = (Get-FileHash -LiteralPath $SourceWingedOrbitalMark -Algorithm SHA256).Hash.ToLowerInvariant()
if (-not [String]::Equals($sourceWingedOrbitalMarkHash, $ApprovedWingedOrbitalMarkSha256, [StringComparison]::Ordinal)) {
    throw "Storyboard winged orbital mark is not approved. Expected SHA-256 $ApprovedWingedOrbitalMarkSha256; got $sourceWingedOrbitalMarkHash."
}
$sourceDesktopBackgroundHash = (Get-FileHash -LiteralPath $SourceDesktopBackground -Algorithm SHA256).Hash.ToLowerInvariant()
if (-not [String]::Equals($sourceDesktopBackgroundHash, $ApprovedDesktopBackgroundSha256, [StringComparison]::Ordinal)) {
    throw "Storyboard desktop background is not approved. Expected SHA-256 $ApprovedDesktopBackgroundSha256; got $sourceDesktopBackgroundHash."
}

$runnerResourceText = [IO.File]::ReadAllText($RunnerResource)
$expectedResourceMetadata = [ordered]@{
    CompanyName = $ExpectedCompanyName
    FileDescription = $ExpectedProductName
    InternalName = $ExpectedInternalName
    LegalCopyright = $ExpectedCopyright
    OriginalFilename = $ExpectedOriginalFilename
    ProductName = $ExpectedProductName
}
foreach ($key in $expectedResourceMetadata.Keys) {
    $expectedValue = $expectedResourceMetadata[$key]
    $pattern = 'VALUE\s+"' + [Regex]::Escape($key) + '"\s*,\s*"' + [Regex]::Escape($expectedValue) + '"\s*"\\0"'
    if (-not [Regex]::IsMatch($runnerResourceText, $pattern, [Text.RegularExpressions.RegexOptions]::CultureInvariant)) {
        throw "windows\runner\Runner.rc does not contain the approved $key metadata value '$expectedValue'."
    }
}

$runnerMainText = [IO.File]::ReadAllText($RunnerMain)
$windowTitlePattern = 'window\.Create\(L"' + [Regex]::Escape($ExpectedWindowTitle) + '"'
if (-not [Regex]::IsMatch($runnerMainText, $windowTitlePattern, [Text.RegularExpressions.RegexOptions]::CultureInvariant)) {
    throw "windows\runner\main.cpp does not use the approved window title '$ExpectedWindowTitle'."
}

Push-Location $SourceRoot
try {
    & $Dart format --output=none --set-exit-if-changed lib test
    if ($LASTEXITCODE -ne 0) { throw "dart format gate failed." }
    & $Flutter analyze
    if ($LASTEXITCODE -ne 0) { throw "flutter analyze gate failed." }
    & $Flutter test --reporter expanded
    if ($LASTEXITCODE -ne 0) { throw "flutter test gate failed." }
    & $Flutter build windows --release
    if ($LASTEXITCODE -ne 0) { throw "flutter build windows gate failed." }
}
finally {
    Pop-Location
}

$BuiltRoot = Join-Path $SourceRoot "build\windows\x64\runner\Release"
$BuiltExe = Join-Path $BuiltRoot "storyboard_movie_creator.exe"
if (-not (Test-Path -LiteralPath $BuiltExe -PathType Leaf)) {
    throw "The verified Flutter release executable was not produced."
}

$builtVersionInfo = (Get-Item -LiteralPath $BuiltExe).VersionInfo
$expectedBuiltMetadata = [ordered]@{
    CompanyName = $ExpectedCompanyName
    FileDescription = $ExpectedProductName
    FileVersion = $Version
    InternalName = $ExpectedInternalName
    LegalCopyright = $ExpectedCopyright
    OriginalFilename = $ExpectedOriginalFilename
    ProductName = $ExpectedProductName
    ProductVersion = $Version
}
foreach ($key in $expectedBuiltMetadata.Keys) {
    $actualValue = [string]$builtVersionInfo.$key
    $expectedValue = [string]$expectedBuiltMetadata[$key]
    if (-not [String]::Equals($actualValue, $expectedValue, [StringComparison]::Ordinal)) {
        throw "Built executable metadata gate failed for $key. Expected '$expectedValue'; got '$actualValue'."
    }
}

if (Test-Path -LiteralPath $ReleaseRoot) {
    $resolvedRelease = [IO.Path]::GetFullPath($ReleaseRoot)
    if (-not $resolvedRelease.StartsWith($releasePrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to replace an output outside release-staged."
    }
    Remove-Item -LiteralPath $resolvedRelease -Recurse -Force
}
New-Item -ItemType Directory -Path $ReleaseRoot | Out-Null
$PackageRoot = Join-Path $ReleaseRoot "dist\StoryboardMovieCreator"
New-Item -ItemType Directory -Path $PackageRoot | Out-Null
Copy-Item -Path (Join-Path $BuiltRoot '*') -Destination $PackageRoot -Recurse -Force
Copy-Item -Path (Join-Path $MaterialsRoot '*') -Destination $PackageRoot -Recurse -Force
Set-Content -LiteralPath (Join-Path $PackageRoot "VERSION.txt") -Value $Version -Encoding utf8

$PackagedWingedOrbitalMark = Join-Path $PackageRoot "data\flutter_assets\assets\branding\engel-winged-orbital-mark.png"
$PackagedDesktopBackground = Join-Path $PackageRoot "data\flutter_assets\assets\branding\engel-desktop-bg.png"
if (-not (Test-Path -LiteralPath $PackagedWingedOrbitalMark -PathType Leaf)) {
    throw "The approved Engel winged orbital mark is missing from the built Flutter assets."
}
if (-not (Test-Path -LiteralPath $PackagedDesktopBackground -PathType Leaf)) {
    throw "The approved Engel desktop background is missing from the built Flutter assets."
}
$packagedWingedOrbitalMarkHash = (Get-FileHash -LiteralPath $PackagedWingedOrbitalMark -Algorithm SHA256).Hash.ToLowerInvariant()
if (-not [String]::Equals($packagedWingedOrbitalMarkHash, $ApprovedWingedOrbitalMarkSha256, [StringComparison]::Ordinal)) {
    throw "The packaged Engel winged orbital mark hash differs from the approved source asset."
}
$packagedDesktopBackgroundHash = (Get-FileHash -LiteralPath $PackagedDesktopBackground -Algorithm SHA256).Hash.ToLowerInvariant()
if (-not [String]::Equals($packagedDesktopBackgroundHash, $ApprovedDesktopBackgroundSha256, [StringComparison]::Ordinal)) {
    throw "The packaged Engel desktop background hash differs from the approved source asset."
}

$textExtensions = @('.txt', '.md', '.json', '.yaml', '.yml', '.xml', '.manifest', '.cmd')
$privatePatterns = @(
    'C:\\Users\\',
    'D:\\b\.WorkSpace',
    '(?i)(api[_-]?key|secret|password)\s*[:=]\s*[^\s\"'']+',
    '(?<!\d)(?:10\.|127\.0\.0\.1|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.)\d{1,3}(?:\.\d{1,3}){2}(?!\d)'
)
foreach ($file in Get-ChildItem -LiteralPath $PackageRoot -Recurse -File) {
    if ($textExtensions -notcontains $file.Extension.ToLowerInvariant()) { continue }
    $content = [IO.File]::ReadAllText($file.FullName)
    foreach ($pattern in $privatePatterns) {
        if ($content -match $pattern) {
            throw "Privacy scan rejected packaged text: $($file.FullName)"
        }
    }
}

$hashRows = @()
foreach ($file in Get-ChildItem -LiteralPath $PackageRoot -Recurse -File | Sort-Object FullName) {
    $relative = Get-PortableRelativePath -BasePath $PackageRoot -ChildPath $file.FullName
    if ($relative -in @('BUILD-MANIFEST.json', 'SHA256SUMS.txt')) { continue }
    $hashRows += [ordered]@{
        path = $relative
        bytes = $file.Length
        sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}
$manifest = [ordered]@{
    schema = "engel_storyboard_movie_creator_release_manifest_v1"
    product = $ExpectedProductName
    publisher = $ExpectedCompanyName
    version = $Version
    version_slug = $VersionSlug
    platform = "windows-x64"
    packaged_at_utc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    signed = $false
    publisher_warning = "Unsigned tester build; Windows may show Unknown Publisher."
    local_first = $true
    private_project_data_included = $false
    branding = [ordered]@{
        company_name = $ExpectedCompanyName
        file_description = $ExpectedProductName
        product_name = $ExpectedProductName
        internal_name = $ExpectedInternalName
        original_filename = $ExpectedOriginalFilename
        legal_copyright = $ExpectedCopyright
        window_title = $ExpectedWindowTitle
        approved_icon_sha256 = $ApprovedIconSha256
        approved_winged_orbital_mark_path = "data/flutter_assets/assets/branding/engel-winged-orbital-mark.png"
        approved_winged_orbital_mark_sha256 = $ApprovedWingedOrbitalMarkSha256
        approved_desktop_background_path = "data/flutter_assets/assets/branding/engel-desktop-bg.png"
        approved_desktop_background_sha256 = $ApprovedDesktopBackgroundSha256
    }
    gates = $RequiredGates
    files = $hashRows
}
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $PackageRoot "BUILD-MANIFEST.json") -Encoding utf8

$sumLines = foreach ($file in Get-ChildItem -LiteralPath $PackageRoot -Recurse -File | Sort-Object FullName) {
    if ($file.Name -eq 'SHA256SUMS.txt') { continue }
    $relative = Get-PortableRelativePath -BasePath $PackageRoot -ChildPath $file.FullName
    $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $relative"
}
$sumLines | Set-Content -LiteralPath (Join-Path $PackageRoot "SHA256SUMS.txt") -Encoding ascii

$ZipPath = Join-Path $ReleaseRoot "StoryboardMovieCreator-$VersionSlug-win-x64.zip"
Compress-Archive -Path (Join-Path $PackageRoot '*') -DestinationPath $ZipPath -CompressionLevel Optimal
$ZipHash = (Get-FileHash -LiteralPath $ZipPath -Algorithm SHA256).Hash.ToLowerInvariant()
"$ZipHash  $([IO.Path]::GetFileName($ZipPath))" | Set-Content -LiteralPath ($ZipPath + '.sha256.txt') -Encoding ascii

& $Python $Verifier --package $PackageRoot --zip $ZipPath
if ($LASTEXITCODE -ne 0) { throw "Storyboard tester package verification failed." }

[ordered]@{
    ok = $true
    package = $PackageRoot
    zip = $ZipPath
    zip_sha256 = $ZipHash
    signed = $false
} | ConvertTo-Json
