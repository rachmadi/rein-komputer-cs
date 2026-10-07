# start_all.ps1 — Menjalankan Backend, Telegram Bot, dan Cloudflare Tunnel sekaligus
$ErrorActionPreference = "Continue"

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "   BOBBY COMPUTER AI SYSTEM — STARTUP SCRIPT          " -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan

# 1. Menjalankan Backend FastAPI & Web Flutter
Write-Host "`n[1/3] Menjalankan FastAPI & Web di port 8000..." -ForegroundColor Yellow
$fastapi = Start-Process -FilePath "$PSScriptRoot\.venv\Scripts\uvicorn.exe" -ArgumentList "app.main:app", "--host", "0.0.0.0", "--port", "8000" -PassThru -WindowStyle Hidden
Write-Host "      FastAPI aktif (PID: $($fastapi.Id))" -ForegroundColor Green

# 2. Menjalankan Bot Telegram
Write-Host "`n[2/3] Menjalankan Bot Telegram (@BobcomCCBot)..." -ForegroundColor Yellow
$tgBot = Start-Process -FilePath "$PSScriptRoot\.venv\Scripts\python.exe" -ArgumentList "$PSScriptRoot\telegram_bot.py" -PassThru -WindowStyle Hidden
Write-Host "      Bot Telegram aktif (PID: $($tgBot.Id))" -ForegroundColor Green

# 3. Menjalankan Cloudflare Tunnel di jendela terminal saat ini agar URL publik tampil
Write-Host "`n[3/3] Menghubungkan ke Cloudflare Tunnel publik (HTTPS gratis)..." -ForegroundColor Yellow
Write-Host "      Tunggu beberapa detik hingga URL *.trycloudflare.com muncul di bawah ini." -ForegroundColor Gray
Write-Host "      Tekan Ctrl+C untuk menutup tunnel.`n" -ForegroundColor Gray

& "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://localhost:8000
