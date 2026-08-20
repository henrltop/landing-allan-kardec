@echo off
rem Coleta horaria do Instagram (agendada no Agendador de Tarefas do Windows).
rem Em producao na VM, o equivalente e um cron rodando: manage.py instagram_sync --auto
cd /d C:\Users\Cyber\Desktop\allan
set PYTHONIOENCODING=utf-8
python manage.py instagram_sync --auto >> sync_instagram.log 2>&1
