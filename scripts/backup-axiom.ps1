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

function Invoke-VerifiedDownload {
    param(
        [string]$Uri,
        [hashtable]$Headers,
        [string]$OutFile
    )

    try {
        $request = @{
            Uri = $Uri
            Headers = $Headers
            OutFile = $OutFile
            UseBasicParsing = $true
        }
        Invoke-WebRequest @request
    }
    catch {
        $detail = $_.Exception.Message
        try {
            if ($null -ne $_.Exception.Response) {
                $stream = $_.Exception.Response.GetResponseStream()
                if ($null -ne $stream) {
                    $reader = New-Object System.IO.StreamReader($stream)
                    try {
                        $body = $reader.ReadToEnd()
                        if (-not [string]::IsNullOrWhiteSpace($body)) {
                            $detail += " Server response: " + $body
                        }
                    }
                    finally {
                        $reader.Dispose()
                    }
                }
            }
        }
        catch {
        }
        throw $detail
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
        "Add a second independent destination such as OneDrive or an external drive."
    )
}

Assert-Command "git"
Assert-Command "tar.exe"

if (-not (Test-Path (Join-Path $RepoRoot ".git"))) {
    throw "RepoRoot is not the AICognitiveMind Git repository: $RepoRoot"
}

if ([string]::IsNullOrWhiteSpace($MindUrl)) {
    $MindUrl = Read-Host "Axiom base URL"
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
$evidenceStage = Join-Path ([IO.Path]::GetTempPath()) ($checkpointName + "-evidence")

if (Test-Path $tempRoot) {
    Remove-Item $tempRoot -Recurse -Force
}
if (Test-Path $evidenceStage) {
    Remove-Item $evidenceStage -Recurse -Force
}
New-Item -ItemType Directory -Path $tempRoot | Out-Null
New-Item -ItemType Directory -Path $evidenceStage | Out-Null

try {
    $gitBundle = Join-Path $tempRoot "repository.bundle"
    $projectZip = Join-Path $tempRoot "working-project.zip"
    $mindZip = Join-Path $tempRoot "axiom.zip"
    $evidenceZip = Join-Path $tempRoot "axiom-evidence.zip"

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

    Invoke-VerifiedDownload -Uri "$MindUrl/v1/admin/backup" -Headers $headers -OutFile $mindZip

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::OpenRead($mindZip)
    try {
        $manifestEntry = $archive.GetEntry("manifest.json")
        if ($null -eq $manifestEntry) {
            throw "Mind snapshot does not contain manifest.json"
        }

        $indexEntry = $archive.GetEntry("evidence/index.json")
        if ($null -eq $indexEntry) {
            throw "Mind snapshot does not contain evidence/index.json"
        }

        $reader = New-Object System.IO.StreamReader($indexEntry.Open())
        try {
            $indexJson = $reader.ReadToEnd()
        }
        finally {
            $reader.Dispose()
        }
    }
    finally {
        $archive.Dispose()
    }

    $evidenceItems = @()
    if (-not [string]::IsNullOrWhiteSpace($indexJson)) {
        $parsedEvidence = $indexJson | ConvertFrom-Json
        if ($null -ne $parsedEvidence) {
            $evidenceItems = @($parsedEvidence)
        }
    }

    $indexJson | Set-Content -Path (Join-Path $evidenceStage "index.json") -Encoding UTF8

    Write-Host (
        "Downloading sensory evidence one artifact at a time (" +
        $evidenceItems.Count +
        " artifact(s))..."
    )

    foreach ($item in $evidenceItems) {
        $relativePath = [string]$item.archive_path
        if (
            [string]::IsNullOrWhiteSpace($relativePath) -or
            $relativePath.Contains("..")
        ) {
            throw "Mind snapshot contains an unsafe evidence archive path"
        }

        $relativePath = $relativePath.Replace(
            "/",
            [IO.Path]::DirectorySeparatorChar
        )
        $targetFile = Join-Path $evidenceStage $relativePath
        $targetDirectory = Split-Path -Parent $targetFile
        New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null

        $capturedAt = [Uri]::EscapeDataString([string]$item.captured_at)
        $evidenceUri = (
            "$MindUrl/v1/evidence/" +
            [string]$item.sha256 +
            "?captured_at=" +
            $capturedAt
        )

        Invoke-VerifiedDownload -Uri $evidenceUri -Headers $headers -OutFile $targetFile

        $downloaded = Get-Item $targetFile
        if ($downloaded.Length -ne [long]$item.byte_length) {
            throw (
                "Evidence byte-length verification failed for " +
                [string]$item.sha256
            )
        }

        $actualHash = (
            Get-FileHash -Path $targetFile -Algorithm SHA256
        ).Hash.ToLowerInvariant()
        $expectedHash = ([string]$item.sha256).ToLowerInvariant()
        if ($actualHash -ne $expectedHash) {
            throw (
                "Evidence SHA-256 verification failed for " +
                [string]$item.sha256
            )
        }
    }

    Write-Host "Archiving verified sensory evidence..."
    & tar.exe -a -c -f $evidenceZip -C $evidenceStage .
    if ($LASTEXITCODE -ne 0) {
        throw "sensory evidence archive failed"
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
        evidence_count = $evidenceItems.Count
        contents = @(
            "repository.bundle",
            "working-project.zip",
            "axiom.zip",
            "axiom-evidence.zip",
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
    if (Test-Path $evidenceStage) {
        Remove-Item $evidenceStage -Recurse -Force
    }
}
