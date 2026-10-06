param(
    [string]$TreeJson = "experiments/toolbox_screening/modelscope_tree_page1.json",
    [string]$OutputRoot = "experiments/toolbox_screening/vendor/modelscope"
)

$ErrorActionPreference = "Stop"
$repository = "aemilia/AIGCDetectionBenchMark"
$endpoint = "https://modelscope.cn/api/v1/datasets/$repository/repo"
$tree = Get-Content -LiteralPath $TreeJson -Raw | ConvertFrom-Json
if ($tree.Code -ne 200) { throw "ModelScope tree API returned code $($tree.Code)" }

$files = @($tree.Data.Files | Where-Object {
    $_.Type -eq "blob" -and ($_.Path -eq "README.md" -or $_.Path -like "PatchCraft/*")
})
if ($files.Count -lt 10) { throw "Expected PatchCraft source entries were missing from the saved official tree." }

foreach ($file in $files) {
    $revision = $file.Revision
    if ([string]::IsNullOrWhiteSpace($revision)) { throw "Missing pinned file revision for $($file.Path)" }
    $destination = Join-Path $OutputRoot ($file.Path -replace '/', [IO.Path]::DirectorySeparatorChar)
    $parent = Split-Path -Parent $destination
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $temporary = "$destination.part"
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }

    & curl.exe -fLsS --connect-timeout 10 --max-time 120 --get `
        --data-urlencode "Revision=$revision" `
        --data-urlencode "FilePath=$($file.Path)" `
        $endpoint -o $temporary
    if ($LASTEXITCODE -ne 0) { throw "Download failed for $($file.Path), curl exit $LASTEXITCODE" }

    $actualSize = (Get-Item -LiteralPath $temporary).Length
    $actualHash = (Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash.ToLowerInvariant()
    $expectedHash = $file.Sha256.ToLowerInvariant()
    if ($actualSize -ne [long]$file.Size -or $actualHash -ne $expectedHash) {
        throw "Integrity check failed for $($file.Path): size=$actualSize hash=$actualHash expectedSize=$($file.Size) expectedHash=$expectedHash"
    }
    Move-Item -LiteralPath $temporary -Destination $destination -Force
    Write-Output "verified`t$($file.Path)`t$actualSize`t$actualHash"
}
