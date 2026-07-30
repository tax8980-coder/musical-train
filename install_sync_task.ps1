# =====================================================================
# 세무칼럼 자동 동기화 - Windows 작업 스케줄러 등록 스크립트
#
#   노션 '세무법인 지율 · 세무칼럼' 페이지의 하위 글을 30분마다
#   자동으로 홈페이지에 반영합니다.
#
# 사전 준비:
#   1) 노션 통합 생성 + '세무칼럼' 페이지 공유 (sync_notion.py 상단 주석 참고)
#   2) 토큰 저장:  setx NOTION_TOKEN "secret_xxxx"   (창을 새로 연 뒤 아래 실행)
#
# 실행:
#   PowerShell 에서  ./install_sync_task.ps1
#   (제거하려면    ./install_sync_task.ps1 -Remove )
# =====================================================================
param([switch]$Remove)

$ErrorActionPreference = "Stop"
$TaskName   = "JiyulNotionColumnSync"
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python     = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $Python) { Write-Error "python 을 찾을 수 없습니다. Python 설치 후 다시 실행하세요."; return }

if ($Remove) {
  if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "작업 '$TaskName' 을 제거했습니다."
  } else { Write-Host "등록된 작업이 없습니다." }
  return
}

if (-not $env:NOTION_TOKEN) {
  Write-Warning "현재 창에 NOTION_TOKEN 이 없습니다. 'setx NOTION_TOKEN ...' 후 새 창에서 다시 실행하세요."
  Write-Warning "작업은 등록하되, 토큰이 없으면 동기화는 건너뜁니다."
}

$action  = New-ScheduledTaskAction -Execute $Python -Argument "`"$ScriptDir\sync_notion.py`"" -WorkingDirectory $ScriptDir
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 30)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
  -Description "노션 세무칼럼 → 홈페이지 자동 동기화 (30분 주기)" -Force | Out-Null

Write-Host "작업 '$TaskName' 등록 완료 — 30분마다 자동 동기화합니다."
Write-Host "지금 즉시 한 번 실행하려면:  Start-ScheduledTask -TaskName $TaskName"
