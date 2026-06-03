$done = Get-ChildItem 'E:\ProgrammingData\python\cfd++changer\gui_src_cn' -Filter '*.tcl' | Select-Object -ExpandProperty Name
$all = Get-ChildItem 'D:\software\CFD++\METACOMP\mlib\mcfd.18.5\exec\gui_src' -Filter '*.tcl' | Select-Object -ExpandProperty Name
$remaining = $all | Where-Object { $done -notcontains $_ }
Write-Host "Done: $($done.Count)"
Write-Host "Remaining: $($remaining.Count)"
Write-Host ""
$remaining | ForEach-Object { Write-Host $_ }