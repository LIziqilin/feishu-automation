# -*- coding: utf-8 -*-
# Path B: daily sync latest recovery-drill backup to Feishu Drive folder [jianli-beidi-beifen]
# Uploads only if filename not already present (dedup by name). Uses drive/v1/files/upload_all
# Field order required: file_name -> parent_type -> parent_node -> size -> file
param(
    [string]$BackupDir = "",
    [string]$FolderToken = "VadKfzxXDlDSZHdXPqEczdk5nUb",
    [string]$EnvPath = "C:\Users\Administrator\AppData\Local\hermes\profiles\agent6_scheduler\scripts\feishu_insight_link.env"
)

$ErrorActionPreference = "Stop"

# Real backup path assembled byte-by-byte to avoid GBK mojibake of the Chinese folder name
# Real backup path assembled byte-by-byte (UTF-8) to avoid GBK mojibake of the Chinese folder name
# D:\AI-Tools\feishu\  +  V13方案增强  +  \backups
$bytes = [byte[]]@(
    0x44,0x3A,0x5C,0x41,0x49,0x2D,0x54,0x6F,0x6F,0x6C,0x73,0x5C,0x66,0x65,0x69,0x73,0x68,0x75,0x5C,
    0x56,0x31,0x33,0xE6,0x96,0xB9,0xE6,0xA1,0x88,0xE5,0xA2,0x9E,0xE5,0xBC,0xBA,
    0x5C,0x62,0x61,0x63,0x6B,0x75,0x70,0x73
)
$RealBackupDir = [System.Text.Encoding]::UTF8.GetString($bytes)
if (-not $BackupDir) { $BackupDir = $RealBackupDir }

function Load-Secret($key) {
    $v = [Environment]::GetEnvironmentVariable($key)
    if ($v) { return $v }
    if (Test-Path $EnvPath) {
        foreach ($line in (Get-Content $EnvPath -Encoding UTF8)) {
            $line = $line.Trim()
            if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
                $idx = $line.IndexOf("=")
                if ($idx -gt 0) {
                    $k = $line.Substring(0, $idx).Trim()
                    $val = $line.Substring($idx + 1).Trim()
                    if ($k -eq $key) { return $val }
                }
            }
        }
    }
    return ""
}

function Get-Token {
    $id = Load-Secret "FEISHU_APP_ID"
    $sec = Load-Secret "FEISHU_APP_SECRET"
    $body = @{ app_id = $id; app_secret = $sec } | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal" `
        -Method Post -ContentType "application/json" -Body $body
    return $r.tenant_access_token
}

function Get-ExistingNames($tok, $folder) {
    $url = "https://open.feishu.cn/open-apis/drive/v1/files?folder_token=$folder&page_size=50"
    $r = Invoke-RestMethod -Uri $url -Headers @{ Authorization = "Bearer $tok" }
    if ($r.data.files) { return ($r.data.files | ForEach-Object { $_.name }) }
    return @()
}

function Upload-All($tok, $file, $folder) {
    $bin = [System.IO.File]::ReadAllBytes($file)
    $boundary = [System.Guid]::NewGuid().ToString()
    $enc = [System.Text.Encoding]::UTF8
    $ms = [System.IO.MemoryStream]::new()
    function AddText($s) { $b = $enc.GetBytes($s); $ms.Write($b, 0, $b.Length) }
    AddText "--$boundary`r`n"
    AddText "Content-Disposition: form-data; name=`"file_name`"`r`n`r`n"
    AddText "$(Split-Path $file -Leaf)`r`n"
    AddText "--$boundary`r`n"
    AddText "Content-Disposition: form-data; name=`"parent_type`"`r`n`r`n"
    AddText "explorer`r`n"
    AddText "--$boundary`r`n"
    AddText "Content-Disposition: form-data; name=`"parent_node`"`r`n`r`n"
    AddText "$folder`r`n"
    AddText "--$boundary`r`n"
    AddText "Content-Disposition: form-data; name=`"size`"`r`n`r`n"
    AddText "$($bin.Length)`r`n"
    AddText "--$boundary`r`n"
    AddText "Content-Disposition: form-data; name=`"file`"; filename=`"$(Split-Path $file -Leaf)`"`r`n"
    AddText "Content-Type: application/json`r`n`r`n"
    $ms.Write($bin, 0, $bin.Length)
    AddText "`r`n--$boundary--`r`n"
    $data = $ms.ToArray()
    return Invoke-RestMethod -Uri "https://open.feishu.cn/open-apis/drive/v1/files/upload_all" `
        -Method Post -ContentType "multipart/form-data; boundary=$boundary" -Body $data `
        -Headers @{ Authorization = "Bearer $tok" }
}

$tok = Get-Token
$latest = Get-ChildItem $BackupDir -Filter "backup_*.json" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $latest) { Write-Host "NO_BACKUP_FILE"; exit 1 }
$existing = Get-ExistingNames $tok $FolderToken
if ($existing -contains $latest.Name) {
    Write-Host "SKIP_ALREADY_SYNCED: $($latest.Name)"
    exit 0
}
$r = Upload-All $tok $latest.FullName $FolderToken
if ($r.code -eq 0) {
    Write-Host "UPLOADED: $($latest.Name) -> $($r.data.url)"
} else {
    Write-Host "UPLOAD_FAIL code=$($r.code) msg=$($r.msg)"
    exit 1
}
