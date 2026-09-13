# JLPT N2 Trainer — 启动脚本（Windows PowerShell）
# -X utf8 必须加：Azure Speech SDK 依赖 UTF-8 filesystem encoding 才能正确合成日文

$env:PYTHONUTF8 = "1"
Set-Location "$PSScriptRoot\backend"
python -X utf8 -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
