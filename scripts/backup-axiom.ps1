# Copyright (c) 2026 William Enright. All rights reserved.
# Use, reproduction, modification, distribution, or commercial exploitation
# of this file is prohibited without prior written permission from the
# copyright holder.

param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot),
    [string[]]$Destination,
    [string]$MindUrl = $env:AXIOM_MIND_URL,
    [string]$MindUsername = $(if ($env:AXIOM_MIND_USERNAME) { $env:AXIOM_MIND_USERNAME } else { "mind" }),
    [string]$MindPassword = $env:AXIOM_MIND_PASSWORD,
    [string]$AdminPin = $env:AXIOM_ADMIN_PIN
)

$ErrorActionPreference = "Stop"

function Read-SecretPlainText {
    param([string]$Prompt)

    $secure = Read-Host $Prompt -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

function Add-DefaultDestinations {
    $items = New-Object System.Collections.Generic.List[string]

    $local = Join-Path $env:USERPROFILE "Documents\AxiomBackups"
    $items.Add($local)

    if ($env:OneDrive) {
        $oneDrive = Join-Path $env:OneDrive "AxiomBackups"
        if ($oneDrive -ne $local) {
            $items.Add($oneDrive)
        }
    }

    return $items.ToArray()
}

function Assert-Command {
    param([string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command was not found: $Name"
    }
}

if (-not $Destination -or $Destination.Count -eq 0) {
    $Destination = Add-DefaultDestinations
}

$Destination = @(
    $Destination |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
        ForEach-Object { [IO.Path]::GetFullPath($_) } |
        Select-Object -Unique
)

if ($Destination.Count -lt 2) {
    Write-Warning (
        "Only one backup destination is available. " +
        "Add a second destination such as an external drive with " +
        "-Destination @('C:\path1','E:\AxiomBackups')."
    )
}

Assert-Command "git"
Assert-Command "tar.exe"

if (-not (Test-Path (Join-Path $RepoRoot ".git"))) {
    throw "RepoRoot is not the AICognitiveMind Git repository: $RepoRoot"
}

if ([string]::IsNullOrWhiteSpace($MindUrl)) {
    $MindUrl = Read-Host "Axiom Mind base URL"
}
$MindUrl = $MindUrl.TrimEnd("/")

if ([string]::IsNullOrWhiteSpace($MindPassword)) {
    $MindPassword = Read-SecretPlainText "Mind password"
}

if ($null -eq $AdminPin) {
    $AdminPin = Read-SecretPlainText "Admin PIN (press Enter if none)"
}

$timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$checkpointName = "Axiom-$timestamp"
$tempRoot = Join-Path ([IO.Path]::GetTempPath()) $checkpointName

if (Test-Path $tempRoot) {
    Remove-Item $tempRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $tempRoot | Out-Null

try {
    $gitBundle = Join-Path $tempRoot "repository.bundle"
    $projectZip = Join-Path $tempRoot "working-project.zip"
    $mindZip = Join-Path $tempRoot "axiom-mind.zip"

    Write-Host "Creating complete Git history bundle..."
    & git -C $RepoRoot bundle create $gitBundle --all
    if ($LASTEXITCODE -ne 0) {
        throw "git bundle create failed"
    }

    & git -C $RepoRoot bundle verify $gitBundle | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "git bundle verification failed"
    }

    Write-Host "Archiving working project and local Genesis Bodies..."
    $tarArgs = @(
        "-a", "-c", "-f", $projectZip,
        "--exclude=.git",
        "--exclude=.env",
        "--exclude=.env.*",
        "--exclude=body-unity/Library",
        "--exclude=body-unity/Temp",
        "--exclude=body-unity/Logs",
        "--exclude=body-unity/obj",
        "--exclude=.vs",
        "--exclude=bin",
        "--exclude=obj",
        "-C", $RepoRoot,
        "."
    )
    & tar.exe @tarArgs
    if ($LASTEXITCODE -ne 0) {
        throw "working project archive failed"
    }

    Write-Host "Downloading protected Mind snapshot..."
    $authText = $MindUsername + ":" + $MindPassword
    $authBytes = [Text.Encoding]::UTF8.GetBytes($authText)
    $headers = @{
        Authorization = "Basic " + [Convert]::ToBase64String($authBytes)
    }
    if (-not [string]::IsNullOrWhiteSpace($AdminPin)) {
        $headers["X-Admin-Pin"] = $AdminPin
    }

    $request = @{
        Uri = "$MindUrl/v1/admin/backup"
        Headers = $headers
        OutFile = $mindZip
        UseBasicParsing = $true
    }
    Invoke-WebRequest @request

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::OpenRead($mindZip)
    try {
        $manifestEntry = $archive.GetEntry("manifest.json")
        if ($null -eq $manifestEntry) {
            throw "Mind snapshot does not contain manifest.json"
        }
    }
    finally {
        $archive.Dispose()
    }

    $head = (& git -C $RepoRoot rev-parse HEAD).Trim()
    $branch = (& git -C $RepoRoot branch --show-current).Trim()
    $status = (& git -C $RepoRoot status --short) -join [Environment]::NewLine

    $metadata = [ordered]@{
        created_at_utc = (Get-Date).ToUniversalTime().ToString("o")
        repository = "Moto1231/AICognitiveMind"
        git_head = $head
        git_branch = $branch
        mind_url = $MindUrl
        contents = @(
            "repository.bundle",
            "working-project.zip",
            "axiom-mind.zip",
            "working-tree-status.txt",
            "SHA256SUMS.txt"
        )
        secrets_in_manifest = $false
    }
    $metadata |
        ConvertTo-Json -Depth 5 |
        Set-Content -Path (Join-Path $tempRoot "checkpoint.json") -Encoding UTF8

    $status |
        Set-Content -Path (Join-Path $tempRoot "working-tree-status.txt") -Encoding UTF8

    $hashLines = foreach ($file in Get-ChildItem $tempRoot -File) {
        if ($file.Name -eq "SHA256SUMS.txt") {
            continue
        }
        $hash = Get-FileHash -Path $file.FullName -Algorithm SHA256
        "$($hash.Hash.ToLowerInvariant())  $($file.Name)"
    }
    $hashLines |
        Set-Content -Path (Join-Path $tempRoot "SHA256SUMS.txt") -Encoding ASCII

    foreach ($destinationRoot in $Destination) {
        New-Item -ItemType Directory -Path $destinationRoot -Force | Out-Null
        $target = Join-Path $destinationRoot $checkpointName

        if (Test-Path $target) {
            throw "Backup target already exists: $target"
        }

        Write-Host "Copying checkpoint to $target"
        Copy-Item $tempRoot $target -Recurse

        foreach ($sourceFile in Get-ChildItem $tempRoot -File) {
            $targetFile = Join-Path $target $sourceFile.Name
            $sourceHash = (Get-FileHash $sourceFile.FullName -Algorithm SHA256).Hash
            $targetHash = (Get-FileHash $targetFile -Algorithm SHA256).Hash
            if ($sourceHash -ne $targetHash) {
                throw "Backup verification failed for $targetFile"
            }
        }
    }

    Write-Host ""
    Write-Host "Axiom backup completed and verified."
    foreach ($destinationRoot in $Destination) {
        Write-Host ("  " + (Join-Path $destinationRoot $checkpointName))
    }
}
finally {
    $MindPassword = $null
    $AdminPin = $null

    if (Test-Path $tempRoot) {
        Remove-Item $tempRoot -Recurse -Force
    }
}
