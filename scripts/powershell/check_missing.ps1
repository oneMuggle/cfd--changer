$done = (Get-Content 'E:\ProgrammingData\python\cfd++changer\translate_v2_progress.json' | ConvertFrom-Json).PSObject.Properties.Name
$src = Get-ChildItem 'E:\ProgrammingData\python\cfd++changer\html' -Filter '*.html' | Select-Object -ExpandProperty Name
$dst = Get-ChildItem 'E:\ProgrammingData\python\cfd++changer\html_cn' -Filter '*.html' | Select-Object -ExpandProperty Name

Write-Host "Progress: $($done.Count) done"
Write-Host "Source: $($src.Count) files"
Write-Host "Translated: $($dst.Count) files"
Write-Host ""

$notInDst = $src | Where-Object { $_ -notin $dst }
if ($notInDst) {
    Write-Host "Not in html_cn: $($notInDst.Count)"
    $notInDst | ForEach-Object { Write-Host "  - $_" }
}

$inDst = $dst | Where-Object { $_ -notin $src }
if ($inDst) {
    Write-Host "Extra in html_cn: $($inDst.Count)"
    $inDst | ForEach-Object { Write-Host "  + $_" }
}