"""Script para agendar coleta diaria via Windows Task Scheduler ou cron."""
import subprocess
import sys
from pathlib import Path


def instalar_windows():
    comando = (
        f'schtasks /Create /SC DAILY /TN "BTGIntelligenceColeta" '
        f'/TR "{sys.executable} {Path(__file__).resolve().parent.parent / 'main.py'}" '
        f'/ST 08:00 /F'
    )
    subprocess.run(comando, shell=True)
    print("Tarefa agendada: BTGIntelligenceColeta (diaria as 08:00)")


def instalar_unix():
    cron_line = f"0 8 * * * cd {Path(__file__).resolve().parent.parent} && {sys.executable} main.py\n"
    print("Adicione ao crontab:")
    print(cron_line)


if __name__ == "__main__":
    if sys.platform == "win32":
        instalar_windows()
    else:
        instalar_unix()
