$content = [System.IO.File]::ReadAllText('E:\ProgrammingData\python\cfd++changer\html\bc_descriptions.html', [System.Text.Encoding]::GetEncoding('GB2312'))
[System.IO.File]::WriteAllText('E:\ProgrammingData\python\cfd++changer\html_cn\bc_descriptions.html', $content, [System.Text.Encoding]::UTF8)
Write-Output 'done'
