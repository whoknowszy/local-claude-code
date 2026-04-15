#!/bin/bash
# tools/setup.ps1 - Universal installation script for lccg (Windows PowerShell)

$LatestVersion = "0.4.1"
$BaseUrl = "https://github.com/whoknowszy/local-claude-code/releases/download/v${LatestVersion}"

function Get-Platform {
    $os = $PSVersionTable.OS
    $arch = $env:PROCESSOR_ARCHITECTURE

    if ($os -like "*Linux*") {
        switch ($arch) {
            "AMD64" { return "linux-x64" }
            "ARM64" { return "linux-arm64" }
            default { return "linux-x64" }
        }
    } elseif ($os -like "*Windows*") {
        switch ($arch) {
            "AMD64" { return "windows-x64" }
            "ARM64" { return "windows-arm64" }
            default { return "windows-x64" }
        }
    } elseif ($os -like "*Darwin*") {
        switch ($arch) {
            "AMD64" { return "macos-x64" }
            "ARM64" { return "macos-arm64" }
            default { return "macos-x64" }
        }
    }
}

function Invoke-Download {
    param($url, $output)
    if (Get-Command Invoke-WebRequest -ErrorAction SilentlyContinue) {
        Invoke-WebRequest -Uri $url -OutFile $output
    } elseif (Get-Command curl -ErrorAction SilentlyContinue) {
        curl -L -o $output $url
    } else {
        Write-Error "Neither Invoke-WebRequest nor curl is available"
        exit 1
    }
}

$platform = Get-Platform
$pyzFile = "lccg-${platform}.pyz"
$targetDir = ${env:LOCALAPPDATA} + "\bin"

if ($env:LCCG_DIR) {
    $targetDir = $env:LCCG_DIR
}

Write-Host "Installing lccg for platform: $platform"

if (!(Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir -Force
}

Write-Host "Downloading $pyzFile..."
Invoke-Download -url "$BaseUrl/$pyzFile" -output "$targetDir\$pyzFile"

Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force

Write-Host "Creating lccg shortcut..."
$targetFile = "$targetDir\lccg.ps1"
Set-Content -Path $targetFile -Value "& '$targetDir\$pyzFile' @args"

Write-Host "Installation complete. Run 'lccg' to start the gateway."