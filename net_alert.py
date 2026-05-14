#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Система мониторинга доступности сетевых устройств
Network Alert System - автоматическая проверка доступности по ping
"""

import json
import time
import subprocess
import requests
import logging
from datetime import datetime
from pathlib import Path
import sys

# ============ НАСТРОЙКИ ============
# Telegram параметры (переменные окружения или конфиг)
TOKEN = "YOUR_BOT_TOKEN"           # Получить от @BotFather
CHAT_ID = "YOUR_CHAT_ID"           # Получить от @userinfobot

CHECK_INTERVAL = 300               # 5 минут между проверками
LOG_FILE = "alerts.log"
CONFIG_FILE = "devices.json"

# Хранилище статуса устройств
device_status = {}                 # Для отслеживания смены статуса

# ============ ЛОГИРОВАНИЕ ============
def setup_logging():
    """Настройка логирования в файл и консоль"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# ============ ВАЛИДАЦИЯ КОНФИГУРАЦИИ ============
def validate_telegram_config():
    """
    Валидация конфигурации Telegram
    
    Returns:
        tuple: (is_valid: bool, error_message: str)
    """
    # Проверка TOKEN
    if not TOKEN or TOKEN == "YOUR_BOT_TOKEN" or len(TOKEN.strip()) < 10:
        return False, "❌ TOKEN не настроен или некорректен. Укажите валидный токен."
    
    # Проверка CHAT_ID
    if not CHAT_ID or CHAT_ID == "YOUR_CHAT_ID" or len(str(CHAT_ID).strip()) == 0:
        return False, "❌ CHAT_ID не настроен. Укажите ID чата."
    
    # Проверка формата TOKEN (должен быть формата: числа:строка)
    if ':' not in TOKEN:
        return False, "❌ Неверный формат TOKEN. Ожидается: <bot_id>:<token>"
    
    return True, "✅ Конфигурация Telegram валидна"

# ============ TELEGRAM ============
def send_telegram(message):
    """
    Отправка сообщения в Telegram
    
    Args:
        message (str): Текст сообщения
    
    Returns:
        bool: True если отправлено успешно, False иначе
    """
    is_valid, error_msg = validate_telegram_config()
    if not is_valid:
        if not hasattr(send_telegram, '_warned'):
            logger.warning(error_msg)
            send_telegram._warned = True
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": message}
        response = requests.post(url, data=data, timeout=5)
        
        if response.status_code == 200:
            return True
        else:
            logger.error(f"Ошибка Telegram API: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка отправки в Telegram: {e}")
        return False
    except Exception as e:
        logger.error(f"Неизвестная ошибка при отправке: {e}")
        return False

# ============ PING ============
def ping(ip, count=1, timeout=2):
    """
    Проверка доступности хоста по ping
    
    Args:
        ip (str): IP-адрес для проверки
        count (int): Количество пакетов
        timeout (int): Таймаут в секундах
    
    Returns:
        bool: True если хост доступен, False иначе
    """
    try:
        # Для Windows используем: ping -n <count> -w <timeout*1000> <ip>
        # Для Linux/Mac используем: ping -c <count> -W <timeout*1000> <ip>
        
        if sys.platform.startswith('win'):
            # Windows
            cmd = ['ping', '-n', str(count), '-w', str(timeout * 1000), ip]
        else:
            # Linux/Mac
            cmd = ['ping', '-c', str(count), '-W', str(timeout * 1000), ip]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout + 1
        )
        return result.returncode == 0
    
    except subprocess.TimeoutExpired:
        return False
    except Exception as e:
        logger.error(f"Ошибка ping для {ip}: {e}")
        return False

# ============ ЗАГРУЗКА КОНФИГУРАЦИИ ============
def load_devices():
    """
    Загрузка списка устройств из JSON файла
    
    Returns:
        list: Список словарей с устройствами
    """
    try:
        config_path = Path(CONFIG_FILE)
        
        if not config_path.exists():
            logger.error(f"Файл конфигурации {CONFIG_FILE} не найден!")
            return []
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            devices = config.get('devices', [])
            
            if not devices:
                logger.warning("Список устройств пуст!")
            
            return devices
    
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON: {e}")
        return []
    except Exception as e:
        logger.error(f"Ошибка загрузки конфигурации: {e}")
        return []

# ============ ОСНОВНОЙ ЦИКЛ ============
def check_devices(devices):
    """
    Проверка доступности всех устройств
    
    Args:
        devices (list): Список устройств для проверки
    """
    logger.info("=" * 60)
    logger.info(f"Проверка доступности {len(devices)} устройств")
    logger.info("=" * 60)
    
    for device in devices:
        name = device.get('name', 'Unknown')
        ip = device.get('ip')
        
        if not ip:
            logger.warning(f"Устройство '{name}' не имеет IP-адреса!")
            continue
        
        # Проверка ping
        is_reachable = ping(ip)
        
        # Проверка изменения статуса
        previous_status = device_status.get(ip)
        device_status[ip] = is_reachable
        
        if is_reachable:
            msg = f"✅ {name} ({ip}) доступен"
            print(msg)
            logger.info(msg)
            
            # Отправляем уведомление о восстановлении если статус изменился
            if previous_status is False:  # Было недоступно, теперь доступно
                detailed_msg = f"🟢 Сетевое устройство восстановлено\n\n"
                detailed_msg += f"Устройство: {name}\n"
                detailed_msg += f"IP-адрес: {ip}\n"
                detailed_msg += f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                detailed_msg += f"Статус: ✅ ДОСТУПНО"
                
                if send_telegram(detailed_msg):
                    logger.info(f"📱 Уведомление о восстановлении отправлено в Telegram для {name}")
        else:
            # Устройство недоступно
            msg = f"⚠️  ALERT: {name} ({ip}) НЕДОСТУПЕН!"
            print(msg)
            logger.warning(msg)
            
            # Отправляем алерт только если статус изменился
            if previous_status is None or previous_status:
                detailed_msg = f"🔴 Сетевое устройство недоступно\n\n"
                detailed_msg += f"Устройство: {name}\n"
                detailed_msg += f"IP-адрес: {ip}\n"
                detailed_msg += f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                detailed_msg += f"Статус: ❌ НЕДОСТУПНО"
                
                if send_telegram(detailed_msg):
                    logger.info(f"📱 Уведомление отправлено в Telegram для {name}")
    
    logger.info("=" * 60 + "\n")

def main():
    """Главная функция"""
    # Валидация конфигурации при запуске
    is_valid, config_msg = validate_telegram_config()
    if not is_valid:
        logger.warning(config_msg)
        logger.warning("⚠️  Уведомления в Telegram будут отключены!")
    else:
        logger.info(config_msg)
    
    devices = load_devices()
    
    if not devices:
        logger.error("Невозможно продолжить: нет устройств для мониторинга!")
        return
    
    logger.info(f"✨ Запуск системы мониторинга доступности сети")
    logger.info(f"📋 Загружено устройств: {len(devices)}")
    logger.info(f"⏰ Интервал проверки: {CHECK_INTERVAL} секунд ({CHECK_INTERVAL // 60} минут)")
    logger.info(f"📁 Лог-файл: {LOG_FILE}")
    
    try:
        check_devices(devices)  # Первая проверка сразу
        
        while True:
            logger.info(f"⏳ Ожидание {CHECK_INTERVAL} секунд до следующей проверки...")
            time.sleep(CHECK_INTERVAL)
            check_devices(devices)
    
    except KeyboardInterrupt:
        logger.info("\n🛑 Мониторинг остановлен пользователем (Ctrl+C)")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        raise

if __name__ == "__main__":
    main()
