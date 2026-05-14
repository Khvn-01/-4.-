import json
import time
import subprocess
import requests
import logging
import sys
import threading
from datetime import datetime
from pathlib import Path

# config
TOKEN = "8531136869:AAEc20dsQo8jJZ1CYmIBLCilBoI16sLQ9TM"
CHAT_ID = "1213695468"

CHECK_INTERVAL = 300  
# Файл для сохранения логов
LOG_FILE = "alerts.txt"
CONFIG_FILE = "devices.json"

device_status = {}

GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

# loggin
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    return logging.getLogger(__name__)

logger = setup_logging()

# tgc
def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
        requests.post(url, data=data, timeout=5)
        return True
    except Exception as e:
        logger.error(f"Ошибка Telegram: {e}")
        return False

# multichannel
def ping_worker(device, results):
    name = device.get('name', 'Неизвестно')
    ip = device.get('ip')
    
    param = '-n' if sys.platform.startswith('win') else '-c'
    timeout_param = '-w' if sys.platform.startswith('win') else '-W'
    timeout_val = '1000' if sys.platform.startswith('win') else '1'
    
    cmd = ['ping', param, '1', timeout_param, timeout_val, ip]
    
    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    is_reachable = (res.returncode == 0)
    
    results.append({
        "name": name,
        "ip": ip,
        "status": is_reachable
    })

def countdown_timer(seconds):
    for i in range(seconds, 0, -1):
        sys.stdout.write(f"\r⏳ До следующей проверки: {i} сек...   ")
        sys.stdout.flush()
        time.sleep(1)
    sys.stdout.write("\r🚀 Запуск проверки...                       \n")

# Main
def run_cycle(devices):
    session_time = datetime.now().strftime('%H:%M:%S')
    print(f"\n{YELLOW}--- Сессия мониторинга: {session_time} ---{RESET}")
    
    # Делаем отметку в файле о начале новой сессии
    logger.info(f"--- Запуск сессии проверки сети ---")
    
    threads = []
    results = []

    for dev in devices:
        t = threading.Thread(target=ping_worker, args=(dev, results))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    for res in results:
        name, ip, is_up = res['name'], res['ip'], res['status']
        
        prev = device_status.get(name)
        device_status[name] = is_up

        color = GREEN if is_up else RED
        status_text = "В СЕТИ " if is_up else "ОШИБКА "
        
        # Вывод на экран с цветом
        print(f"[{color}{status_text}{RESET}] {name:20} | {ip}")
        
        # log history
        logger.info(f"Статус узла: {name} ({ip}) - {status_text.strip()}")

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # notification
        if prev != is_up:
            if not is_up:
                msg = (
                    f"<b>Сетевое устройство недоступно</b>\n\n"
                    f"Устройство: {name}\n"
                    f"IP-адрес: {ip}\n"
                    f"Время: {current_time}\n"
                    f"Статус: ❌ НЕДОСТУПНО"
                )
                send_telegram(msg)
                logger.warning(f"ОТПРАВЛЕН АЛЕРТ: {name} упал!")

            elif is_up and prev is False:
                msg = (
                    f"<b>Сетевое устройство доступно (Восстановление)</b>\n\n"
                    f"Устройство: {name}\n"
                    f"IP-адрес: {ip}\n"
                    f"Время: {current_time}\n"
                    f"Статус: ✅ ДОСТУПНО"
                )
                send_telegram(msg)
                logger.info(f"ОТПРАВЛЕН АЛЕРТ: {name} восстановлен!")

def load_devices():
    try:
        if not Path(CONFIG_FILE).exists():
            example = [
                {"name": "Router-R1", "ip": "8.8.8.8"},
                {"name": "Broken-Server", "ip": "192.168.1.255"}
            ]
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(example, f, indent=4, ensure_ascii=False)
            return example
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка чтения JSON: {e}")
        return []

def main():
    if sys.platform.startswith('win'):
        import os
        os.system('chcp 65001 > nul')

    try:
        print(f"{GREEN}✨ Система мониторинга запущена!{RESET}")
        
        # Записываем старт в текстовый файл
        logger.info("Скрипт успешно запущен. Начинаем мониторинг устройств.")
        
        while True:
            devices = load_devices()
            if devices:
                run_cycle(devices)
            countdown_timer(CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        print(f"\n{YELLOW}🛑 Мониторинг остановлен.{RESET}")
        logger.info("Скрипт остановлен пользователем (Ctrl+C).")

if __name__ == "__main__":
    main()
