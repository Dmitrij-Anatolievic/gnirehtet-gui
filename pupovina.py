#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pupovina — reverse tethering Android via USB (interfaccia grafica per gnirehtet)
(il telefono usa la connessione internet del PC tramite cavo USB).

Basata su gnirehtet di Genymobile (Apache 2.0):
https://github.com/Genymobile/gnirehtet

Funziona su Windows e Linux. Richiede: Python 3.9+ e PyQt6
    pip install PyQt6

Autore: Dmitrij Musella — © 2026
"""

from __future__ import annotations

__author__ = "Dmitrij Musella"
__version__ = "1.4.0"

import getpass
import hashlib
import html
import json
import os
import re
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import (
    QLibraryInfo, QLocale, QObject, QProcess, QSettings, Qt, QTimer, QTranslator, QUrl, pyqtSignal,
)
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtGui import (
    QAction, QActionGroup, QBrush, QColor, QDesktopServices, QIcon, QPainter, QPen, QPixmap,
)
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QPushButton,
    QSpinBox, QSplitter, QSystemTrayIcon, QTableWidget, QTableWidgetItem,
    QTextBrowser, QVBoxLayout, QWidget,
)

# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

APP_NAME = "Pupovina"  # fino alla 1.3.0: "Gnirehtet GUI"
GNIREHTET_VERSION = "2.5.1"
PACKAGE = "com.genymobile.gnirehtet"
DEFAULT_PORT = 31416
POLL_MS = 2000
NO_TRAFFIC_HINT_S = 20      # dopo quanti secondi senza traffico avvisare

IS_WIN = sys.platform.startswith("win")
IS_LINUX = sys.platform.startswith("linux")
EXE = ".exe" if IS_WIN else ""
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if IS_WIN else 0

_GH = f"https://github.com/Genymobile/gnirehtet/releases/download/v{GNIREHTET_VERSION}"
DOWNLOADS = {
    "gnirehtet": {
        "win": (f"{_GH}/gnirehtet-rust-win64-v{GNIREHTET_VERSION}.zip",
                "7f5b1063e7895182aa60def1437e50363c3758144088dcd079037bb7c3c46a1c"),
        "linux": (f"{_GH}/gnirehtet-rust-linux64-v{GNIREHTET_VERSION}.zip",
                  "dee55499ca4fef00ce2559c767d2d8130163736d43fdbce753e923e75309c275"),
    },
    "adb": {
        "win": ("https://dl.google.com/android/repository/platform-tools-latest-windows.zip", None),
        "linux": ("https://dl.google.com/android/repository/platform-tools-latest-linux.zip", None),
    },
}
SDK_REPOSITORY_URLS = (
    "https://dl.google.com/android/repository/repository2-3.xml",
    "https://dl.google.com/android/repository/repository2-1.xml",
)

# Stati del tethering
ST_IDLE, ST_BUSY, ST_ACTIVE, ST_ERROR = "idle", "busy", "active", "error"

LANGUAGES = {"it": "Italiano", "en": "English", "ru": "Русский"}
LANG = "it"   # impostata all'avvio


def app_dir() -> Path:
    if getattr(sys, "frozen", False):  # eseguibile PyInstaller
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def data_dir() -> Path:
    """Cartella dati fissa nel profilo utente: non dipende da dove si trova il programma."""
    if IS_WIN:
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "GnirehtetGUI"   # nome storico: mantiene strumenti e impostazioni delle versioni precedenti


TOOLS_DIR = data_dir() / "tools"
LEGACY_TOOLS_DIR = app_dir() / "tools"   # posizione usata dalla versione 1.0


def platform_key() -> str | None:
    return "win" if IS_WIN else ("linux" if IS_LINUX else None)


# ---------------------------------------------------------------------------
# Traduzioni
# ---------------------------------------------------------------------------

S: dict[str, tuple[str, str, str]] = {
    # chiave: (italiano, english, русский)
    "tools": ("Strumenti", "Tools", "Инструменты"),
    "dl_gn": ("Scarica gnirehtet {v}", "Download gnirehtet {v}", "Скачать gnirehtet {v}"),
    "dl_adb": ("Scarica adb (platform-tools)", "Download adb (platform-tools)",
               "Скачать adb (platform-tools)"),
    "upd_adb": ("Aggiorna adb", "Update adb", "Обновить adb"),
    "relay": ("Relay:", "Relay:", "Ретранслятор:"),
    "folder": ("Cartella:", "Folder:", "Папка:"),
    "open_folder": ("Apri cartella strumenti", "Open tools folder", "Открыть папку инструментов"),
    "not_found": ("✘ non trovato", "✘ not found", "✘ не найден"),
    "version": ("versione {v}", "version {v}", "версия {v}"),
    "relay_on": ("● in esecuzione", "● running", "● работает"),
    "relay_port": ("(porta {p})", "(port {p})", "(порт {p})"),
    "relay_off": ("○ fermo", "○ stopped", "○ остановлен"),
    "relay_off_note": ("(parte da solo al primo avvio del tethering)",
                       "(starts automatically with the first tethering)",
                       "(запускается сам при первом включении тетеринга)"),
    "devices": ("Dispositivi collegati", "Connected devices", "Подключённые устройства"),
    "col_device": ("Dispositivo", "Device", "Устройство"),
    "col_serial": ("Seriale", "Serial", "Серийный номер"),
    "col_adb": ("Stato ADB", "ADB state", "Состояние ADB"),
    "col_tether": ("Tethering", "Tethering", "Тетеринг"),
    "col_speed": ("Velocità", "Speed", "Скорость"),
    "col_traffic": ("Traffico", "Traffic", "Трафик"),
    "no_devices": ("Nessun dispositivo. Collega il telefono via USB con il <b>debug USB</b> "
                   "attivo (Opzioni sviluppatore).",
                   "No devices. Connect the phone via USB with <b>USB debugging</b> enabled "
                   "(Developer options).",
                   "Устройств нет. Подключите телефон по USB с включённой <b>отладкой по USB</b> "
                   "(Параметры разработчика)."),
    "btn_start": ("▶  Avvia tethering", "▶  Start tethering", "▶  Включить тетеринг"),
    "btn_stop": ("■  Ferma", "■  Stop", "■  Остановить"),
    "btn_tunnel": ("↻  Ripristina tunnel", "↻  Reset tunnel", "↻  Восстановить туннель"),
    "tunnel_tip": ("Utile se la connessione si blocca dopo aver ricollegato il cavo",
                   "Useful if the connection hangs after replugging the cable",
                   "Помогает, если связь зависла после переподключения кабеля"),
    "autorun": ("Autorun: attiva su ogni telefono che colleghi",
                "Autorun: enable on every phone you plug in",
                "Автозапуск: включать на каждом подключённом телефоне"),
    "btn_settings": ("Impostazioni…", "Settings…", "Настройки…"),
    "console": ("Console", "Console", "Консоль"),
    "copy_all": ("Copia tutto", "Copy all", "Копировать всё"),
    "clear": ("Pulisci", "Clear", "Очистить"),
    # menu
    "m_file": ("&File", "&File", "&Файл"),
    "m_settings": ("Impostazioni…", "Settings…", "Настройки…"),
    "m_quit": ("Esci", "Quit", "Выход"),
    "m_lang": ("&Lingua", "&Language", "&Язык"),
    "m_help": ("&Aiuto", "&Help", "&Справка"),
    "m_manual": ("Manuale utente", "User manual", "Руководство пользователя"),
    "m_about": ("Informazioni su {app}", "About {app}", "О программе {app}"),
    "about": ("<h3>{app} {ver}</h3><p>Interfaccia grafica per il reverse tethering Android.</p>"
              "<p><b>Autore:</b> {author}<br>© 2026 {author}</p>"
              "<p>Basata su <a href='https://github.com/Genymobile/gnirehtet'>gnirehtet</a> "
              "di Genymobile (licenza Apache 2.0).</p>",
              "<h3>{app} {ver}</h3><p>Graphical interface for Android reverse tethering.</p>"
              "<p><b>Author:</b> {author}<br>© 2026 {author}</p>"
              "<p>Based on <a href='https://github.com/Genymobile/gnirehtet'>gnirehtet</a> "
              "by Genymobile (Apache 2.0 license).</p>",
              "<h3>{app} {ver}</h3><p>Графический интерфейс для обратного тетеринга Android.</p>"
              "<p><b>Автор:</b> {author}<br>© 2026 {author}</p>"
              "<p>Основано на <a href='https://github.com/Genymobile/gnirehtet'>gnirehtet</a> "
              "от Genymobile (лицензия Apache 2.0).</p>"),
    "lang_title": ("Lingua", "Language", "Язык"),
    "lang_restart": ("La nuova lingua sarà attiva al riavvio. Riavviare ora?",
                     "The new language takes effect after a restart. Restart now?",
                     "Новый язык будет применён после перезапуска. Перезапустить сейчас?"),
    # stati
    "st_idle": ("Spento", "Off", "Выключен"),
    "st_busy": ("In corso…", "Working…", "Выполняется…"),
    "st_active": ("Attivo", "Active", "Активен"),
    "st_error": ("Errore", "Error", "Ошибка"),
    "no_traffic": ("nessun traffico finora", "no traffic yet", "трафика пока нет"),
    "vpn_off": ("VPN non attiva sul telefono?", "VPN not active on the phone?",
                "VPN на телефоне не активен?"),
    "queued": ("In coda…", "Queued…", "В очереди…"),
    "checking_app": ("Controllo app…", "Checking app…", "Проверка приложения…"),
    "installing_app": ("Installazione app…", "Installing app…", "Установка приложения…"),
    "starting": ("Avvio…", "Starting…", "Запуск…"),
    "stopping": ("Arresto…", "Stopping…", "Остановка…"),
    "resetting": ("Ripristino tunnel…", "Resetting tunnel…", "Восстановление туннеля…"),
    "adb_device": ("Pronto", "Ready", "Готов"),
    "adb_unauthorized": ("Non autorizzato: accetta il debug sul telefono",
                         "Unauthorized: allow debugging on the phone",
                         "Не авторизован: разрешите отладку на телефоне"),
    "adb_offline": ("Offline", "Offline", "Не в сети"),
    "adb_no permissions": ("Permessi USB mancanti (regole udev)",
                           "Missing USB permissions (udev rules)",
                           "Нет прав USB (правила udev)"),
    "adb_recovery": ("Recovery", "Recovery", "Recovery"),
    "adb_sideload": ("Sideload", "Sideload", "Sideload"),
    # log
    "log_ready": ("{app} {ver} pronto. Cartella strumenti: {dir}",
                  "{app} {ver} ready. Tools folder: {dir}",
                  "{app} {ver} готов. Папка инструментов: {dir}"),
    "log_missing": ("Strumenti mancanti: premi «Scarica» nel riquadro in alto.",
                    "Tools missing: press «Download» in the panel at the top.",
                    "Нет инструментов: нажмите «Скачать» в панели сверху."),
    "err_tools": ("Mancano gnirehtet o adb: usa i pulsanti «Scarica» in alto o indica i "
                  "percorsi nelle Impostazioni.",
                  "gnirehtet or adb is missing: use the «Download» buttons at the top or set "
                  "the paths in Settings.",
                  "Не найден gnirehtet или adb: нажмите «Скачать» сверху или укажите пути "
                  "в Настройках."),
    "log_connected": ("Collegato: {name} ({state})", "Connected: {name} ({state})",
                      "Подключено: {name} ({state})"),
    "log_disconnected": ("Scollegato: {name}", "Disconnected: {name}", "Отключено: {name}"),
    "log_will_reconnect": ("{name} scollegato: lo riattivo quando torna.",
                           "{name} disconnected: it will be re-enabled when it comes back.",
                           "{name} отключён: тетеринг включится снова, когда он вернётся."),
    "log_autorun_on": ("Autorun attivato.", "Autorun enabled.", "Автозапуск включён."),
    "log_autorun_off": ("Autorun disattivato.", "Autorun disabled.", "Автозапуск выключен."),
    "log_vpn_first": ("Prima volta su questo telefono: conferma la richiesta di connessione VPN "
                      "che compare sullo schermo.",
                      "First time on this phone: confirm the VPN connection request shown on "
                      "the screen.",
                      "Первый запуск на этом телефоне: подтвердите запрос VPN-подключения "
                      "на экране."),
    "log_active": ("Tethering attivo su {name}.", "Tethering active on {name}.",
                   "Тетеринг активен на {name}."),
    "err_relay": ("relay non avviato", "relay not started", "ретранслятор не запущен"),
    "err_install": ("installazione fallita", "installation failed", "установка не удалась"),
    "err_code": ("codice {code}", "code {code}", "код {code}"),
    "err_cmd": ("{cmd}: codice {code}", "{cmd}: code {code}", "{cmd}: код {code}"),
    "relay_closed": ("relay chiuso", "relay closed", "ретранслятор закрыт"),
    "log_relay_early": ("Il relay si è chiuso subito. Forse la porta è già occupata "
                        "(un altro gnirehtet aperto?).",
                        "The relay exited immediately. The port may already be in use "
                        "(another gnirehtet running?).",
                        "Ретранслятор сразу закрылся. Возможно, порт занят "
                        "(запущен другой gnirehtet?)."),
    "log_port_orphan": ("La porta {p} è occupata da un gnirehtet rimasto aperto: lo chiudo e "
                        "riprovo.",
                        "Port {p} is held by a leftover gnirehtet: closing it and retrying.",
                        "Порт {p} занят оставшимся процессом gnirehtet: закрываю его и "
                        "пробую снова."),
    "log_port_other": ("La porta {p} è occupata da un altro programma. Chiudilo oppure cambia "
                       "la porta del relay nelle Impostazioni.",
                       "Port {p} is used by another program. Close it or change the relay "
                       "port in Settings.",
                       "Порт {p} занят другой программой. Закройте её или смените порт "
                       "ретранслятора в Настройках."),
    "err_port": ("porta {p} occupata", "port {p} in use", "порт {p} занят"),
    "btn_procs": ("Controlla processi", "Check processes", "Проверить процессы"),
    "procs_tip": ("Cerca gnirehtet rimasti aperti e altre copie del programma, e li chiude",
                  "Finds leftover gnirehtet processes and other copies of the program, and "
                  "closes them",
                  "Ищет оставшиеся процессы gnirehtet и другие копии программы и закрывает их"),
    "procs_title": ("Processi già attivi", "Running processes", "Запущенные процессы"),
    "procs_checking": ("Controllo dei processi attivi…", "Checking running processes…",
                       "Проверка запущенных процессов…"),
    "procs_none": ("Nessun processo vecchio trovato: è tutto pulito.",
                   "No leftover processes found: everything is clean.",
                   "Оставшихся процессов не найдено: всё чисто."),
    "procs_intro": ("Questi processi sono rimasti aperti da sessioni precedenti e possono "
                    "bloccare il tethering (porta occupata). Seleziona quelli da chiudere.",
                    "These processes were left open by earlier sessions and can block "
                    "tethering (port in use). Select the ones to close.",
                    "Эти процессы остались от предыдущих сеансов и могут мешать тетерингу "
                    "(порт занят). Выберите, какие закрыть."),
    "procs_kill": ("Chiudi selezionati", "Close selected", "Закрыть выбранные"),
    "col_pid": ("PID", "PID", "PID"),
    "col_kind": ("Tipo", "Type", "Тип"),
    "col_cmd": ("Comando", "Command", "Команда"),
    "kind_relay": ("gnirehtet rimasto aperto", "leftover gnirehtet", "оставшийся gnirehtet"),
    "kind_gui": ("altra copia di Pupovina", "another copy of Pupovina",
                 "другая копия Pupovina"),
    "procs_killed": ("Chiusi {n} processi.", "Closed {n} processes.",
                     "Закрыто процессов: {n}."),
    "procs_kill_fail": ("Impossibile chiudere il processo {pid}: {e}",
                        "Cannot close process {pid}: {e}",
                        "Не удалось закрыть процесс {pid}: {e}"),
    "procs_found": ("Trovati {n} processi rimasti aperti da sessioni precedenti: usa "
                    "«Controlla processi» per chiuderli.",
                    "Found {n} processes left open by earlier sessions: use «Check "
                    "processes» to close them.",
                    "Найдено процессов от предыдущих сеансов: {n}. Закройте их кнопкой "
                    "«Проверить процессы»."),
    "procs_error": ("Impossibile elencare i processi: {e}", "Cannot list processes: {e}",
                    "Не удалось получить список процессов: {e}"),
    "log_relay_fail": ("Impossibile avviare il relay: {e}", "Cannot start the relay: {e}",
                       "Не удалось запустить ретранслятор: {e}"),
    "log_relay_end": ("Relay terminato (codice {code}).", "Relay stopped (code {code}).",
                      "Ретранслятор остановлен (код {code})."),
    "log_next_time": ("Le modifiche a porta e DNS valgono dal prossimo avvio del tethering.",
                      "Port and DNS changes apply from the next tethering start.",
                      "Изменения порта и DNS вступят в силу при следующем запуске тетеринга."),
    "log_error": ("{name}: {detail}", "{name}: {detail}", "{name}: {detail}"),
    "log_dl": ("Scarico {url}", "Downloading {url}", "Загрузка {url}"),
    "log_sha_ok": ("  Checksum SHA-256 verificato.", "  SHA-256 checksum verified.",
                   "  Контрольная сумма SHA-256 проверена."),
    "err_sha": ("checksum SHA-256 non corrispondente: file scartato",
                "SHA-256 checksum mismatch: file discarded",
                "контрольная сумма SHA-256 не совпадает: файл отброшен"),
    "log_installed": ("{what} installato in {dir}", "{what} installed in {dir}",
                      "{what} установлен в {dir}"),
    "log_udev": ("Su Linux, se il telefono risulta «Permessi USB mancanti», installa le regole "
                 "udev (pacchetto android-sdk-platform-tools-common o android-udev-rules).",
                 "On Linux, if the phone shows «Missing USB permissions», install the udev "
                 "rules (package android-sdk-platform-tools-common or android-udev-rules).",
                 "В Linux, если телефон показывает «Нет прав USB», установите правила udev "
                 "(пакет android-sdk-platform-tools-common или android-udev-rules)."),
    "err_dl": ("Download di {what} non riuscito: {e}", "Download of {what} failed: {e}",
               "Не удалось скачать {what}: {e}"),
    "err_platform": ("Download automatico disponibile solo su Windows e Linux.",
                     "Automatic download is available only on Windows and Linux.",
                     "Автоматическая загрузка доступна только в Windows и Linux."),
    # aggiornamento adb
    "upd_checking": ("Controllo aggiornamenti di adb…", "Checking for adb updates…",
                     "Проверка обновлений adb…"),
    "upd_title": ("Aggiornamento adb", "adb update", "Обновление adb"),
    "upd_latest_log": ("adb installato: {cur} — ultima versione: {latest}",
                       "adb installed: {cur} — latest version: {latest}",
                       "Установлен adb: {cur} — последняя версия: {latest}"),
    "upd_ok": ("Hai già l'ultima versione di adb ({cur}).",
               "You already have the latest adb ({cur}).",
               "У вас уже последняя версия adb ({cur})."),
    "upd_available": ("È disponibile adb {latest} (installato: {cur}). Scaricarlo ora?",
                      "adb {latest} is available (installed: {cur}). Download it now?",
                      "Доступен adb {latest} (установлен: {cur}). Скачать сейчас?"),
    "upd_unknown": ("Non riesco a verificare l'ultima versione ({e}).\n"
                    "Vuoi riscaricare comunque l'ultima versione di platform-tools?",
                    "Could not check the latest version ({e}).\n"
                    "Download the latest platform-tools anyway?",
                    "Не удалось проверить последнюю версию ({e}).\n"
                    "Всё равно скачать последнюю версию platform-tools?"),
    "upd_busy": ("Ferma il tethering su tutti i telefoni prima di aggiornare adb.",
                 "Stop tethering on all phones before updating adb.",
                 "Остановите тетеринг на всех телефонах перед обновлением adb."),
    "unknown": ("sconosciuta", "unknown", "неизвестна"),
    # tray e notifiche
    "tray_show": ("Mostra finestra", "Show window", "Показать окно"),
    "tray_autorun": ("Autorun", "Autorun", "Автозапуск"),
    "tray_stop_all": ("Ferma tutto", "Stop all", "Остановить всё"),
    "tray_hint": ("Continuo a funzionare nell'area di notifica.",
                  "Still running in the notification area.",
                  "Программа продолжает работать в области уведомлений."),
    "tray_tip": ("{n} telefono/i in tethering — ↓ {down} ↑ {up}",
                 "{n} phone(s) tethering — ↓ {down} ↑ {up}",
                 "Телефонов в тетеринге: {n} — ↓ {down} ↑ {up}"),
    "n_connected": ("Telefono collegato", "Phone connected", "Телефон подключён"),
    "n_disconnected": ("Telefono scollegato", "Phone disconnected", "Телефон отключён"),
    "n_active": ("Tethering attivo", "Tethering active", "Тетеринг активен"),
    "n_active_msg": ("{name} usa la connessione del computer.",
                     "{name} is using the computer's connection.",
                     "{name} использует подключение компьютера."),
    "n_error": ("Errore di tethering", "Tethering error", "Ошибка тетеринга"),
    # impostazioni
    "set_title": ("Impostazioni", "Settings", "Настройки"),
    "set_gn": ("Percorso gnirehtet:", "gnirehtet path:", "Путь к gnirehtet:"),
    "set_adb": ("Percorso adb:", "adb path:", "Путь к adb:"),
    "set_auto_gn": ("automatico (cartella strumenti o PATH)", "automatic (tools folder or PATH)",
                    "автоматически (папка инструментов или PATH)"),
    "set_auto_adb": ("automatico (variabile ADB, cartella strumenti o PATH)",
                     "automatic (ADB variable, tools folder or PATH)",
                     "автоматически (переменная ADB, папка инструментов или PATH)"),
    "set_port": ("Porta del relay:", "Relay port:", "Порт ретранслятора:"),
    "set_dns": ("Server DNS:", "DNS servers:", "DNS-серверы:"),
    "set_dns_ph": ("es. 1.1.1.1,8.8.8.8 (vuoto = predefinito)",
                   "e.g. 1.1.1.1,8.8.8.8 (empty = default)",
                   "напр. 1.1.1.1,8.8.8.8 (пусто = по умолчанию)"),
    "set_lang": ("Lingua:", "Language:", "Язык:"),
    "set_stop_exit": ("Ferma il tethering sui telefoni quando esci",
                      "Stop tethering on the phones when quitting",
                      "Останавливать тетеринг на телефонах при выходе"),
    "set_hidden": ("Avvia nascosto nell'area di notifica", "Start hidden in the notification area",
                   "Запускать свёрнутым в область уведомлений"),
    "set_notify": ("Mostra notifiche (collegamento, scollegamento, errori)",
                   "Show notifications (connect, disconnect, errors)",
                   "Показывать уведомления (подключение, отключение, ошибки)"),
    "browse": ("Sfoglia…", "Browse…", "Обзор…"),
    "choose_exe": ("Scegli l'eseguibile", "Choose the executable", "Выберите исполняемый файл"),
}

UNITS = {"it": ("B", "KB", "MB", "GB", "/s"), "en": ("B", "KB", "MB", "GB", "/s"),
         "ru": ("Б", "КБ", "МБ", "ГБ", "/с")}


def T(key: str, **kw) -> str:
    text = S[key][("it", "en", "ru").index(LANG)]
    return text.format(**kw) if kw else text


def detect_language(saved: str) -> str:
    if saved in LANGUAGES:
        return saved
    sys_lang = QLocale.system().name()[:2]
    return sys_lang if sys_lang in LANGUAGES else "en"


def fmt_bytes(n: float) -> str:
    units = UNITS[LANG]
    n = float(n)
    for u in units[:3]:
        if n < 1024:
            text = f"{n:.0f} {u}" if u == units[0] else f"{n:.1f} {u}"
            break
        n /= 1024
    else:
        text = f"{n:.2f} {units[3]}"
    return text.replace(".", ",") if LANG in ("it", "ru") else text


def fmt_rate(bps: float) -> str:
    return fmt_bytes(bps) + UNITS[LANG][4]


# ---------------------------------------------------------------------------
# Utilità
# ---------------------------------------------------------------------------

def find_in_tree(root: Path, name: str) -> Path | None:
    if not root.exists():
        return None
    for p in sorted(root.rglob(name)):
        if p.is_file():
            return p
    return None


def _first_file(*candidates) -> Path | None:
    for c in candidates:
        if c and Path(c).is_file():
            return Path(c)
    return None


def locate_gnirehtet(custom: str, remembered: str = "") -> Path | None:
    """Ordine: percorso scelto nelle impostazioni, ultimo trovato, cartelle strumenti, PATH."""
    name = "gnirehtet" + EXE
    return _first_file(
        custom, remembered,
        find_in_tree(TOOLS_DIR, name), find_in_tree(LEGACY_TOOLS_DIR, name),
        shutil.which("gnirehtet"),
    )


def locate_adb(custom: str, remembered: str, gnirehtet: Path | None) -> Path | None:
    name = "adb" + EXE
    return _first_file(
        custom, remembered, os.environ.get("ADB"),
        find_in_tree(TOOLS_DIR, name), find_in_tree(LEGACY_TOOLS_DIR, name),
        gnirehtet.parent / name if gnirehtet else None,
        shutil.which("adb"),
    )


def make_executable(p: Path) -> None:
    if not IS_WIN and p.exists():
        p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def run_cmd(args, env=None, cwd=None, timeout=60) -> tuple[int, str]:
    """Esegue un comando senza aprire finestre di console; restituisce (codice, output)."""
    try:
        r = subprocess.run(
            [str(a) for a in args], capture_output=True, env=env, cwd=cwd,
            timeout=timeout, stdin=subprocess.DEVNULL, creationflags=NO_WINDOW,
        )
        out = (r.stdout + r.stderr).decode("utf-8", "replace").strip()
        return r.returncode, out
    except subprocess.TimeoutExpired:
        return -1, f"timeout ({timeout}s)"
    except OSError as e:
        return -1, str(e)


def port_in_use(port: int) -> bool:
    """True se qualcosa è già in ascolto sulla porta locale."""
    for host in ("127.0.0.1", "::1"):
        fam = socket.AF_INET6 if ":" in host else socket.AF_INET
        try:
            with socket.socket(fam, socket.SOCK_STREAM) as sk:
                sk.settimeout(0.5)
                if sk.connect_ex((host, port)) == 0:
                    return True
        except OSError:
            pass
    return False


def _linux_ancestors(pid: int) -> set[int]:
    out = set()
    while pid > 1 and pid not in out:
        out.add(pid)
        try:
            stat_line = Path(f"/proc/{pid}/stat").read_text()
            pid = int(stat_line.rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            break
    return out


def find_leftover_processes(exclude: set[int]) -> list[tuple[int, str, str]]:
    """Processi gnirehtet e altre copie del programma -> [(pid, 'relay'|'gui', comando)].
    `exclude` contiene i PID da non toccare (questo programma e il suo relay)."""
    found: list[tuple[int, str, str]] = []
    own = {os.getpid(), os.getppid()} | set(exclude)
    if IS_WIN:
        ps = ("Get-CimInstance Win32_Process | Where-Object { "
              "$_.Name -ieq 'gnirehtet.exe' -or $_.Name -ieq 'Pupovina.exe' -or $_.Name -ieq 'GnirehtetGUI.exe' -or "
              "(($_.CommandLine -like '*pupovina.py*' -or $_.CommandLine -like '*gnirehtet_gui*') -and $_.Name -notlike 'powershell*') } | "
              "Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress")
        code, out = run_cmd(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                            timeout=30)
        if code != 0:
            raise RuntimeError(out or f"powershell: {code}")
        if not out.strip():
            return found
        data = json.loads(out)
        for item in data if isinstance(data, list) else [data]:
            pid = int(item.get("ProcessId") or 0)
            name = (item.get("Name") or "").lower()
            if not pid or pid in own:
                continue
            kind = "relay" if name == "gnirehtet.exe" else "gui"
            found.append((pid, kind, item.get("CommandLine") or item.get("Name") or ""))
    else:
        own |= _linux_ancestors(os.getpid())
        for d in Path("/proc").iterdir():
            if not d.name.isdigit():
                continue
            pid = int(d.name)
            if pid in own:
                continue
            try:
                comm = (d / "comm").read_text().strip()
                cmd = (d / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace").strip()
            except OSError:
                continue
            if comm == "gnirehtet":
                found.append((pid, "relay", cmd or comm))
            elif comm.startswith(("Pupovina", "GnirehtetGUI")) or "pupovina.py" in cmd or "gnirehtet_gui" in cmd:
                found.append((pid, "gui", cmd or comm))
    return sorted(found)


def kill_process(pid: int) -> str:
    """Chiude un processo (e i suoi figli su Windows). Restituisce '' o il messaggio d'errore."""
    if IS_WIN:
        code, out = run_cmd(["taskkill", "/F", "/T", "/PID", str(pid)], timeout=15)
        return "" if code == 0 else out
    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(20):
            time.sleep(0.1)
            os.kill(pid, 0)
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return ""
    except OSError as e:
        return str(e)
    return ""


def kill_leftover_relays() -> bool:
    """Chiude i processi gnirehtet rimasti aperti (relay orfani). True se ne ha chiuso almeno uno."""
    if IS_WIN:
        code, _ = run_cmd(["taskkill", "/F", "/T", "/IM", "gnirehtet.exe"], timeout=15)
    else:
        code, _ = run_cmd(["pkill", "-x", "gnirehtet"], timeout=15)
    return code == 0


def fmt_cmd(args) -> str:
    """Comando leggibile per la console: solo il nome del programma, non il percorso."""
    args = [str(a) for a in args]
    return " ".join([Path(args[0]).name, *args[1:]])


def parse_adb_devices(text: str) -> dict[str, tuple[str, str]]:
    """Interpreta l'output di `adb devices -l` -> {seriale: (stato, modello)}."""
    devices: dict[str, tuple[str, str]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices") or line.startswith("*"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        rest = parts[2:]
        if state == "no" and rest[:1] == ["permissions"]:
            state, rest = "no permissions", rest[1:]
        info = dict(p.split(":", 1) for p in rest if ":" in p)
        model = info.get("model", "").replace("_", " ")
        devices[serial] = (state, model)
    return devices


def parse_net_dev(text: str) -> tuple[int, int] | None:
    """Byte ricevuti/inviati dalle interfacce tun del telefono (la VPN di gnirehtet).
    rx = dati arrivati al telefono (download), tx = dati usciti dal telefono (upload)."""
    rx = tx = 0
    found = False
    for line in text.splitlines():
        if ":" not in line:
            continue
        name, data = line.split(":", 1)
        if not name.strip().startswith("tun"):
            continue
        f = data.split()
        if len(f) >= 9 and f[0].isdigit() and f[8].isdigit():
            rx += int(f[0])
            tx += int(f[8])
            found = True
    return (rx, tx) if found else None


def parse_adb_version(text: str) -> tuple[int, ...] | None:
    """Da `adb version` -> (35, 0, 2). Usa la riga 'Version x.y.z-…' (versione platform-tools)."""
    m = re.search(r"^Version\s+(\d+)\.(\d+)\.(\d+)", text, re.MULTILINE)
    return tuple(int(x) for x in m.groups()) if m else None


def parse_latest_platform_tools(xml_bytes: bytes) -> tuple[int, ...] | None:
    """Ultima versione stabile di platform-tools dal repository SDK di Google."""
    root = ET.fromstring(xml_bytes)

    def local(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    best = None
    for pkg in root.iter():
        if local(pkg.tag) != "remotePackage" or pkg.get("path") != "platform-tools":
            continue
        channel = next((c.get("ref") for c in pkg if local(c.tag) == "channelRef"), "channel-0")
        if channel != "channel-0":
            continue
        rev = next((c for c in pkg if local(c.tag) == "revision"), None)
        if rev is None:
            continue
        parts = {local(c.tag): int(c.text or 0) for c in rev}
        v = (parts.get("major", 0), parts.get("minor", 0), parts.get("micro", 0))
        best = max(best, v) if best else v
    return best


def vstr(v: tuple[int, ...] | None) -> str:
    return ".".join(map(str, v)) if v else T("unknown")


def make_icon(color: str, size: int = 64) -> QIcon:
    return QIcon(make_pixmap(color, size))


def make_pixmap(color: str, size: int = 64) -> QPixmap:
    """Icona disegnata al volo: un telefono con un punto di stato."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 64
    p.setPen(QPen(QColor("#2b2f36"), 4 * s))
    p.setBrush(QBrush(QColor("#e9edf2")))
    p.drawRoundedRect(int(16 * s), int(4 * s), int(30 * s), int(54 * s), 6 * s, 6 * s)
    p.setPen(QPen(QColor("#2b2f36"), 3 * s))
    p.drawLine(int(26 * s), int(51 * s), int(36 * s), int(51 * s))
    p.setPen(QPen(QColor("white"), 3 * s))
    p.setBrush(QBrush(QColor(color)))
    p.drawEllipse(int(36 * s), int(34 * s), int(26 * s), int(26 * s))
    p.end()
    return pm


ICON_COLORS = {"idle": "#8a919c", "active": "#2e9d57", "error": "#d64545"}


# ---------------------------------------------------------------------------
# Segnali tra thread di lavoro e interfaccia
# ---------------------------------------------------------------------------

class Bridge(QObject):
    log = pyqtSignal(str, str)                      # livello, testo
    devices = pyqtSignal(dict)                      # risultato di adb devices
    status = pyqtSignal(str, str, str)              # seriale, stato, dettaglio
    relay_state = pyqtSignal(bool)
    tools_changed = pyqtSignal()
    stats = pyqtSignal(str, object, float)          # seriale, (rx, tx) o None, istante
    adb_version = pyqtSignal(object)                # tupla versione o None
    update_check = pyqtSignal(object, object, str)  # attuale, ultima, errore
    procs = pyqtSignal(object, bool, str)           # elenco, richiesto a mano, errore

    def safe_emit(self, sig_name: str, *args) -> None:
        try:
            getattr(self, sig_name).emit(*args)
        except RuntimeError:  # oggetto già distrutto in chiusura
            pass


# ---------------------------------------------------------------------------
# Relay server
# ---------------------------------------------------------------------------

class Relay:
    def __init__(self, bridge: Bridge):
        self.bridge = bridge
        self.proc: subprocess.Popen | None = None
        self.lock = threading.Lock()
        self.last_error = ""

    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self, gnirehtet: Path, env: dict, port: int) -> bool:
        with self.lock:
            if self.running():
                return True
            if port_in_use(port):
                if kill_leftover_relays():
                    self.bridge.safe_emit("log", "warn", T("log_port_orphan", p=port))
                    for _ in range(25):
                        if not port_in_use(port):
                            break
                        time.sleep(0.2)
                if port_in_use(port):
                    self.bridge.safe_emit("log", "err", T("log_port_other", p=port))
                    self.last_error = T("err_port", p=port)
                    return False
            self.last_error = ""
            args = [str(gnirehtet), "relay"]
            if port != DEFAULT_PORT:
                args += ["-p", str(port)]
            self.bridge.safe_emit("log", "cmd", fmt_cmd(args))
            try:
                self.proc = subprocess.Popen(
                    args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL, env=env, cwd=str(gnirehtet.parent),
                    creationflags=NO_WINDOW,
                )
            except OSError as e:
                self.bridge.safe_emit("log", "err", T("log_relay_fail", e=e))
                return False
            threading.Thread(target=self._reader, args=(self.proc,), daemon=True).start()
        time.sleep(0.8)
        if not self.running():
            self.bridge.safe_emit("log", "err", T("log_relay_early"))
            return False
        self.bridge.safe_emit("relay_state", True)
        return True

    def _reader(self, proc: subprocess.Popen) -> None:
        assert proc.stdout is not None
        for raw in iter(proc.stdout.readline, b""):
            line = raw.decode("utf-8", "replace").rstrip()
            if line:
                self.bridge.safe_emit("log", "relay", line)
        proc.wait()
        self.bridge.safe_emit("log", "info", T("log_relay_end", code=proc.returncode))
        self.bridge.safe_emit("relay_state", False)

    def stop(self) -> None:
        with self.lock:
            if not self.running():
                return
            assert self.proc is not None
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()


# ---------------------------------------------------------------------------
# Finestra impostazioni
# ---------------------------------------------------------------------------

class SettingsDialog(QDialog):
    def __init__(self, settings: QSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle(T("set_title"))
        self.settings = settings
        form = QFormLayout(self)

        self.gn_path = QLineEdit(settings.value("gnirehtet_path", "", str))
        self.gn_path.setPlaceholderText(T("set_auto_gn"))
        form.addRow(T("set_gn"), self._with_browse(self.gn_path))

        self.adb_path = QLineEdit(settings.value("adb_path", "", str))
        self.adb_path.setPlaceholderText(T("set_auto_adb"))
        form.addRow(T("set_adb"), self._with_browse(self.adb_path))

        self.port = QSpinBox()
        self.port.setRange(1024, 65535)
        self.port.setValue(int(settings.value("port", DEFAULT_PORT)))
        form.addRow(T("set_port"), self.port)

        self.dns = QLineEdit(settings.value("dns", "", str))
        self.dns.setPlaceholderText(T("set_dns_ph"))
        form.addRow(T("set_dns"), self.dns)

        self.lang = QComboBox()
        for code, name in LANGUAGES.items():
            self.lang.addItem(name, code)
        self.lang.setCurrentIndex(list(LANGUAGES).index(LANG))
        form.addRow(T("set_lang"), self.lang)

        self.notify = QCheckBox(T("set_notify"))
        self.notify.setChecked(settings.value("notifications", True, bool))
        form.addRow(self.notify)

        self.stop_on_exit = QCheckBox(T("set_stop_exit"))
        self.stop_on_exit.setChecked(settings.value("stop_on_exit", True, bool))
        form.addRow(self.stop_on_exit)

        self.start_hidden = QCheckBox(T("set_hidden"))
        self.start_hidden.setChecked(settings.value("start_hidden", False, bool))
        form.addRow(self.start_hidden)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        form.addRow(bb)
        self.resize(600, self.sizeHint().height())

    def _with_browse(self, edit: QLineEdit) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(edit)
        b = QPushButton(T("browse"))
        b.clicked.connect(lambda: self._browse(edit))
        h.addWidget(b)
        return w

    def _browse(self, edit: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(self, T("choose_exe"))
        if path:
            edit.setText(path)

    def chosen_language(self) -> str:
        return self.lang.currentData()

    def _save(self) -> None:
        s = self.settings
        s.setValue("gnirehtet_path", self.gn_path.text().strip())
        s.setValue("adb_path", self.adb_path.text().strip())
        s.setValue("port", self.port.value())
        s.setValue("dns", self.dns.text().replace(" ", ""))
        s.setValue("notifications", self.notify.isChecked())
        s.setValue("stop_on_exit", self.stop_on_exit.isChecked())
        s.setValue("start_hidden", self.start_hidden.isChecked())
        self.accept()


class ProcessesDialog(QDialog):
    """Elenco dei processi rimasti aperti, con caselle per scegliere quali chiudere."""

    def __init__(self, procs: list[tuple[int, str, str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle(T("procs_title"))
        lay = QVBoxLayout(self)
        intro = QLabel(T("procs_intro"))
        intro.setWordWrap(True)
        lay.addWidget(intro)
        self.table = QTableWidget(len(procs), 3)
        self.table.setHorizontalHeaderLabels([T("col_pid"), T("col_kind"), T("col_cmd")])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for row, (pid, kind, cmd) in enumerate(procs):
            item = QTableWidgetItem(str(pid))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, pid)
            self.table.setItem(row, 0, item)
            self.table.setItem(row, 1, QTableWidgetItem(T(f"kind_{kind}")))
            cmd_item = QTableWidgetItem(cmd)
            cmd_item.setToolTip(cmd)
            self.table.setItem(row, 2, cmd_item)
        lay.addWidget(self.table)
        bb = QDialogButtonBox()
        bb.addButton(T("procs_kill"), QDialogButtonBox.ButtonRole.AcceptRole)
        bb.addButton(QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.resize(760, 320)

    def selected_pids(self) -> list[int]:
        out = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item.checkState() == Qt.CheckState.Checked:
                out.append(int(item.data(Qt.ItemDataRole.UserRole)))
        return out


# ---------------------------------------------------------------------------
# Manuale utente (italiano, inglese, russo)
# ---------------------------------------------------------------------------

MANUAL = {}

MANUAL["it"] = """# Manuale utente — {app} {ver}

*di {author}*

## A cosa serve

{app} permette a un telefono Android di **usare la connessione internet del
computer attraverso il cavo USB**. È il contrario del normale hotspot, per questo si
chiama *reverse tethering*. Non serve il root né sul telefono né sul computer.

Il programma è un'interfaccia grafica per **gnirehtet** di Genymobile: fa al posto tuo
tutto quello che altrimenti dovresti digitare nel terminale, e in più mostra velocità e
traffico di ogni telefono.

Funziona su **Windows** e **Linux**, in **italiano, inglese e russo**. Gnirehtet trasporta
il traffico TCP e UDP su IPv4 (IPv6 non è supportato).

## Installazione

**Versione pronta (consigliata)**: dalla pagina *Releases* del progetto su GitHub scarica
`Pupovina.exe` per Windows oppure `Pupovina-x86_64.AppImage` per Linux. Non serve
installare Python. Su Linux rendi eseguibile l'AppImage (`chmod +x`) e avviala.

**Dal codice sorgente**: installa Python 3.9 o superiore e PyQt6 (`pip install PyQt6`),
poi avvia `python pupovina.py`.

Sul telefono servono Android 5.0 o superiore, il **Debug USB** attivo e un cavo USB che
trasporti i dati. Per attivare il Debug USB: *Impostazioni → Informazioni sul telefono*,
tocca sette volte **Numero build** per sbloccare le *Opzioni sviluppatore*, poi in
*Opzioni sviluppatore* attiva **Debug USB**.

## Primo avvio

1. Nel riquadro **Strumenti** premi **Scarica gnirehtet**. Il programma scarica la
   versione ufficiale Rust {gv}, ne verifica l'impronta SHA-256 e la installa.
2. Se adb non è già presente sul computer, premi **Scarica adb (platform-tools)**.
   Viene scaricato dal sito ufficiale Android.
3. Collega il telefono. Sullo schermo compare la richiesta *Consentire il debug USB?*:
   accettala (meglio con *Consenti sempre da questo computer*).
4. Seleziona il telefono nell'elenco e premi **Avvia tethering**.
5. La prima volta l'app gnirehtet viene installata sul telefono, che chiede di
   **consentire una connessione VPN**: conferma. Quando è attiva, nella barra di stato
   del telefono compare l'icona a forma di chiave.

Gli strumenti scaricati restano sul computer, nella cartella:

`{folder}`

Ai successivi avvii vengono ritrovati da soli e non si riscaricano.

## La finestra principale

### Strumenti
Mostra dove si trovano **gnirehtet** e **adb** (✔ trovato, ✘ mancante), la versione di
adb e lo stato del **relay**, il piccolo server che inoltra il traffico del telefono verso
internet. Il relay si avvia da solo al primo tethering e si chiude quando esci.

- **Aggiorna adb** controlla sul sito di Google se esiste una versione più recente di adb
  e, se c'è, la scarica e la installa. Prima di aggiornare va fermato il tethering su tutti
  i telefoni. Se adb era installato nel sistema, da quel momento il programma usa la
  propria copia aggiornata.
- **Apri cartella strumenti** apre la cartella in cui sono salvati gnirehtet e adb.
- **Controlla processi** cerca i gnirehtet rimasti aperti da sessioni precedenti (per
  esempio dopo una chiusura brusca) e le altre copie del programma, li mostra in un elenco
  con PID e comando, e chiude quelli che selezioni. Il relay in uso in questo momento non
  viene mai elencato. Lo stesso controllo parte da solo all'avvio: se trova qualcosa lo
  segnala in console. Il programma inoltre non si apre due volte: una seconda apertura porta
  in primo piano la finestra già aperta.

### Dispositivi collegati
Elenco dei telefoni rilevati da adb, aggiornato ogni 2 secondi.

| Colonna | Significato |
|---|---|
| Dispositivo | Modello del telefono |
| Seriale | Identificativo usato da adb |
| Stato ADB | *Pronto*, *Non autorizzato*, *Offline*, *Permessi USB mancanti* |
| Tethering | *Spento*, operazione in corso, *Attivo* oppure *Errore* con il motivo |
| Velocità | ↓ download e ↑ upload del telefono in questo momento |
| Traffico | Dati scaricati (↓) e inviati (↑) da quando hai avviato il tethering |

Velocità e traffico sono letti direttamente dal telefono, sull'interfaccia della VPN di
gnirehtet: se i numeri si muovono, **la rete passa davvero**. Se dopo una ventina di
secondi il traffico è ancora zero, nella colonna Tethering compare *nessun traffico finora*;
se la VPN non risulta proprio attiva compare *VPN non attiva sul telefono?*, di solito
perché la richiesta VPN non è stata confermata.

Pulsanti:

- **Avvia tethering**: controlla che l'app sia installata sul telefono (la installa se
  manca), avvia il relay se serve e attiva la connessione.
- **Ferma**: spegne la connessione sul telefono selezionato.
- **Ripristina tunnel**: rifà il collegamento tra telefono e computer senza fermare
  tutto. Utile se la rete si blocca dopo aver staccato e riattaccato il cavo.
- **Doppio clic** su una riga: avvia o ferma il tethering di quel telefono.

Puoi collegare **più telefoni contemporaneamente**: ognuno si gestisce dalla sua riga.

### Autorun
Con la casella **Autorun** spuntata il tethering parte da solo su ogni telefono che
colleghi. La scelta viene ricordata.

Indipendentemente dall'autorun, se scolleghi un telefono mentre è attivo, il programma
lo riattiva quando lo ricolleghi.

### Console
Registro di tutto ciò che succede: i comandi eseguiti (in blu), i messaggi del relay
(in grigio), le operazioni riuscite (in verde), gli avvisi (in arancione) e gli errori
(in rosso). **Copia tutto** copia il registro negli appunti, utile per chiedere aiuto;
**Pulisci** lo svuota.

## Icona e notifiche

Chiudendo la finestra il programma **non si chiude**: resta nell'area di notifica,
vicino all'orologio, e il tethering continua a funzionare.

- Icona **grigia**: nessun telefono connesso.
- Icona **verde**: almeno un telefono sta usando la rete del computer.
- Icona **rossa**: c'è un errore.

Passando il mouse sull'icona vedi quanti telefoni sono in tethering e la velocità totale.
Un clic mostra o nasconde la finestra. Con il tasto destro trovi *Mostra finestra*,
*Autorun*, *Ferma tutto* ed **Esci**. Per chiudere davvero il programma usa **Esci**,
dall'icona oppure dal menu *File*.

Il programma mostra una **notifica** quando un telefono viene collegato o scollegato,
quando il tethering diventa attivo e quando si verifica un errore. Le notifiche si
possono disattivare nelle Impostazioni.

## Impostazioni

Dal menu *File → Impostazioni* o dal pulsante **Impostazioni…**:

- **Percorso gnirehtet / adb**: lasciali vuoti per la ricerca automatica, oppure indica
  un eseguibile preciso.
- **Porta del relay**: predefinita 31416. Cambiala solo se è già occupata.
- **Server DNS**: per esempio `1.1.1.1,8.8.8.8`. Vuoto significa usare quelli predefiniti.
- **Lingua**: italiano, inglese o russo (anche dal menu *Lingua*). Alla prima apertura il
  programma usa la lingua del sistema. Il cambio richiede un riavvio, che il programma
  propone di fare subito.
- **Mostra notifiche**: attiva o disattiva le notifiche.
- **Ferma il tethering sui telefoni quando esci**: consigliato, altrimenti la VPN
  resta accesa sul telefono senza portare traffico.
- **Avvia nascosto nell'area di notifica**: il programma parte senza mostrare la finestra.

Le modifiche a porta e DNS valgono dal tethering successivo.

## Avvio da riga di comando

```
python pupovina.py              avvio normale
python pupovina.py --nascosto   avvio direttamente nell'area di notifica
```

L'opzione `--nascosto` (oppure `--hidden`) funziona anche con l'eseguibile e l'AppImage.

## Problemi comuni

**Il telefono non compare nell'elenco**
Controlla che il Debug USB sia attivo e che il cavo trasporti i dati. Su alcuni telefoni
bisogna scegliere la modalità USB *Trasferimento file*.

**Stato «Non autorizzato»**
Sblocca il telefono e accetta la richiesta di debug USB. Se non compare, in
*Opzioni sviluppatore* usa *Revoca autorizzazioni debug USB* e ricollega il cavo.

**Stato «Permessi USB mancanti» (solo Linux)**
Mancano le regole udev per Android: installa `android-sdk-platform-tools-common`
(Debian/Ubuntu) oppure `android-udev-rules` (Arch, Fedora), poi ricollega il cavo.

**«Relay non avviato» o «porta 31416 occupata»**
Un altro programma sta già usando la porta. Se è un gnirehtet rimasto aperto, il programma
lo chiude da solo al momento dell'avvio; puoi anche usare **Controlla processi**. Se è un
programma diverso, chiudilo oppure cambia porta nelle Impostazioni.

**Tethering «Attivo» ma il telefono non naviga**
Guarda le colonne Velocità e Traffico. Se compare *VPN non attiva sul telefono?*, sblocca
il telefono e conferma la richiesta VPN. Se la VPN è attiva ma il traffico resta a zero,
verifica che il computer sia connesso a internet, poi prova **Ripristina tunnel**, oppure
**Ferma** e di nuovo **Avvia**.

**Firewall di Windows**
Al primo avvio del relay Windows può chiedere di consentire l'accesso di rete a
gnirehtet: consentilo almeno per le reti private.

**Windows SmartScreen**
L'eseguibile non è firmato digitalmente, quindi al primo avvio Windows può mostrare
l'avviso *Windows ha protetto il PC*: scegli *Ulteriori informazioni → Esegui comunque*.

## Riservatezza

Il programma non raccoglie né invia dati. Si collega a internet solo quando premi
**Scarica** o **Aggiorna adb**, per prendere gnirehtet da GitHub e adb dal sito di Google.
Le impostazioni restano sul tuo computer.

## Crediti

{app} — © 2026 {author}.

Basato su [gnirehtet](https://github.com/Genymobile/gnirehtet) di Genymobile,
distribuito con licenza Apache 2.0. adb fa parte degli Android SDK Platform Tools di Google.
"""

MANUAL["en"] = """# User manual — {app} {ver}

*by {author}*

## What it does

{app} lets an Android phone **use the computer's internet connection over the USB
cable**. It is the opposite of a normal hotspot, which is why it is called *reverse
tethering*. No root is needed, neither on the phone nor on the computer.

The program is a graphical interface for **gnirehtet** by Genymobile: it does for you
everything you would otherwise type in a terminal, and it also shows the speed and
traffic of each phone.

It works on **Windows** and **Linux**, in **Italian, English and Russian**. Gnirehtet
carries TCP and UDP traffic over IPv4 (IPv6 is not supported).

## Installation

**Ready-made build (recommended)**: from the project's *Releases* page on GitHub download
`Pupovina.exe` for Windows or `Pupovina-x86_64.AppImage` for Linux. Python is not
required. On Linux make the AppImage executable (`chmod +x`) and run it.

**From source**: install Python 3.9 or later and PyQt6 (`pip install PyQt6`), then run
`python pupovina.py`.

The phone needs Android 5.0 or later, **USB debugging** enabled and a USB cable that
carries data. To enable USB debugging: *Settings → About phone*, tap **Build number**
seven times to unlock *Developer options*, then in *Developer options* turn on
**USB debugging**.

## First start

1. In the **Tools** panel press **Download gnirehtet**. The program downloads the official
   Rust version {gv}, verifies its SHA-256 fingerprint and installs it.
2. If adb is not already on the computer, press **Download adb (platform-tools)**.
   It comes from the official Android website.
3. Connect the phone. The prompt *Allow USB debugging?* appears on its screen: accept it
   (preferably with *Always allow from this computer*).
4. Select the phone in the list and press **Start tethering**.
5. The first time, the gnirehtet app is installed on the phone, which asks you to
   **allow a VPN connection**: confirm. When it is active, a key icon appears in the
   phone's status bar.

The downloaded tools stay on the computer, in the folder:

`{folder}`

On later starts they are found automatically and are not downloaded again.

## The main window

### Tools
Shows where **gnirehtet** and **adb** are (✔ found, ✘ missing), the adb version and the
state of the **relay**, the small server that forwards the phone's traffic to the
internet. The relay starts automatically with the first tethering and stops when you quit.

- **Update adb** checks Google's website for a newer adb and, if there is one, downloads
  and installs it. Tethering must be stopped on all phones before updating. If adb was
  installed system-wide, from then on the program uses its own updated copy.
- **Open tools folder** opens the folder where gnirehtet and adb are stored.
- **Check processes** looks for gnirehtet processes left open by earlier sessions (for
  example after a crash) and other copies of the program, lists them with PID and command,
  and closes the ones you select. The relay currently in use is never listed. The same check
  runs by itself at startup and reports any findings in the console. The program also cannot
  be opened twice: a second launch brings the existing window to the front.

### Connected devices
List of the phones detected by adb, refreshed every 2 seconds.

| Column | Meaning |
|---|---|
| Device | Phone model |
| Serial | Identifier used by adb |
| ADB state | *Ready*, *Unauthorized*, *Offline*, *Missing USB permissions* |
| Tethering | *Off*, operation in progress, *Active* or *Error* with the reason |
| Speed | The phone's current ↓ download and ↑ upload |
| Traffic | Data downloaded (↓) and sent (↑) since tethering started |

Speed and traffic are read directly from the phone, on gnirehtet's VPN interface: if the
numbers move, **the network really works**. If traffic is still zero after about twenty
seconds, the Tethering column shows *no traffic yet*; if the VPN is not active at all it
shows *VPN not active on the phone?*, usually because the VPN request was not confirmed.

Buttons:

- **Start tethering**: checks that the app is installed on the phone (installs it if
  missing), starts the relay if needed and enables the connection.
- **Stop**: turns off the connection on the selected phone.
- **Reset tunnel**: rebuilds the link between phone and computer without stopping
  everything. Useful if the network hangs after unplugging and replugging the cable.
- **Double-click** a row: starts or stops tethering on that phone.

You can connect **several phones at once**: each one is managed from its own row.

### Autorun
With the **Autorun** box ticked, tethering starts by itself on every phone you plug in.
The choice is remembered.

Regardless of autorun, if you unplug a phone while it is active, the program re-enables
it when you plug it back in.

### Console
Log of everything that happens: executed commands (blue), relay messages (grey),
successful operations (green), warnings (orange) and errors (red). **Copy all** copies
the log to the clipboard, useful when asking for help; **Clear** empties it.

## Icon and notifications

Closing the window **does not quit** the program: it stays in the notification area,
next to the clock, and tethering keeps working.

- **Grey** icon: no phone connected.
- **Green** icon: at least one phone is using the computer's network.
- **Red** icon: there is an error.

Hovering over the icon shows how many phones are tethering and the total speed. A click
shows or hides the window. Right-click for *Show window*, *Autorun*, *Stop all* and
**Quit**. To really close the program use **Quit**, from the icon or the *File* menu.

The program shows a **notification** when a phone is connected or disconnected, when
tethering becomes active and when an error occurs. Notifications can be turned off in
Settings.

## Settings

From *File → Settings* or the **Settings…** button:

- **gnirehtet / adb path**: leave empty for automatic search, or point to a specific
  executable.
- **Relay port**: default 31416. Change it only if it is already in use.
- **DNS servers**: for example `1.1.1.1,8.8.8.8`. Empty means the defaults.
- **Language**: Italian, English or Russian (also from the *Language* menu). On first start
  the program uses the system language. Changing it requires a restart, which the program
  offers to do right away.
- **Show notifications**: turns notifications on or off.
- **Stop tethering on the phones when quitting**: recommended, otherwise the VPN stays on
  on the phone without carrying traffic.
- **Start hidden in the notification area**: the program starts without showing the window.

Port and DNS changes apply from the next tethering start.

## Command line

```
python pupovina.py            normal start
python pupovina.py --hidden   start directly in the notification area
```

The `--hidden` option also works with the executable and the AppImage.

## Troubleshooting

**The phone does not appear in the list**
Check that USB debugging is enabled and that the cable carries data. On some phones you
need to pick the *File transfer* USB mode.

**State «Unauthorized»**
Unlock the phone and accept the USB debugging prompt. If it does not appear, use
*Revoke USB debugging authorizations* in *Developer options* and replug the cable.

**State «Missing USB permissions» (Linux only)**
The Android udev rules are missing: install `android-sdk-platform-tools-common`
(Debian/Ubuntu) or `android-udev-rules` (Arch, Fedora), then replug the cable.

**«Relay not started» or «port 31416 in use»**
Another program is already using the port. If it is a leftover gnirehtet, the program
closes it automatically when starting; you can also use **Check processes**. If it is a
different program, close it or change the port in Settings.

**Tethering «Active» but the phone cannot browse**
Look at the Speed and Traffic columns. If *VPN not active on the phone?* appears, unlock
the phone and confirm the VPN request. If the VPN is active but traffic stays at zero,
check that the computer is online, then try **Reset tunnel**, or **Stop** and **Start**
again.

**Windows Firewall**
When the relay first starts, Windows may ask to allow network access for gnirehtet:
allow it at least for private networks.

**Windows SmartScreen**
The executable is not digitally signed, so on first launch Windows may show *Windows
protected your PC*: choose *More info → Run anyway*.

## Privacy

The program collects and sends no data. It goes online only when you press **Download**
or **Update adb**, to fetch gnirehtet from GitHub and adb from Google's website.
Settings stay on your computer.

## Credits

{app} — © 2026 {author}.

Based on [gnirehtet](https://github.com/Genymobile/gnirehtet) by Genymobile, released
under the Apache 2.0 license. adb is part of Google's Android SDK Platform Tools.
"""

MANUAL["ru"] = """# Руководство пользователя — {app} {ver}

*автор: {author}*

## Назначение

{app} позволяет телефону Android **пользоваться интернетом компьютера через USB-кабель**.
Это противоположность обычной точке доступа, поэтому такая функция называется
*обратным тетерингом* (reverse tethering). Root-права не нужны ни на телефоне, ни на
компьютере.

Программа — это графический интерфейс для **gnirehtet** от Genymobile: она делает за вас
всё, что иначе пришлось бы вводить в терминале, и вдобавок показывает скорость и трафик
каждого телефона.

Работает в **Windows** и **Linux**, на **итальянском, английском и русском** языках.
Gnirehtet передаёт трафик TCP и UDP по IPv4 (IPv6 не поддерживается).

## Установка

**Готовая сборка (рекомендуется)**: на странице *Releases* проекта на GitHub скачайте
`Pupovina.exe` для Windows или `Pupovina-x86_64.AppImage` для Linux. Python
устанавливать не нужно. В Linux сделайте AppImage исполняемым (`chmod +x`) и запустите.

**Из исходного кода**: установите Python 3.9 или новее и PyQt6 (`pip install PyQt6`),
затем выполните `python pupovina.py`.

На телефоне нужны Android 5.0 или новее, включённая **отладка по USB** и кабель, который
передаёт данные. Как включить отладку: *Настройки → О телефоне*, семь раз нажмите
**Номер сборки**, чтобы открыть *Параметры разработчика*, затем в *Параметрах
разработчика* включите **Отладку по USB**.

## Первый запуск

1. В панели **Инструменты** нажмите **Скачать gnirehtet**. Программа скачает официальную
   версию на Rust {gv}, проверит её отпечаток SHA-256 и установит.
2. Если adb на компьютере ещё нет, нажмите **Скачать adb (platform-tools)**.
   Он загружается с официального сайта Android.
3. Подключите телефон. На экране появится запрос *Разрешить отладку по USB?* —
   подтвердите его (лучше с отметкой *Всегда разрешать с этого компьютера*).
4. Выберите телефон в списке и нажмите **Включить тетеринг**.
5. В первый раз на телефон устанавливается приложение gnirehtet, и телефон просит
   **разрешить VPN-подключение** — подтвердите. Когда оно активно, в строке состояния
   телефона появляется значок ключа.

Скачанные инструменты остаются на компьютере, в папке:

`{folder}`

При следующих запусках они находятся автоматически и повторно не скачиваются.

## Главное окно

### Инструменты
Показывает, где находятся **gnirehtet** и **adb** (✔ найден, ✘ отсутствует), версию adb
и состояние **ретранслятора** — небольшого сервера, который передаёт трафик телефона в
интернет. Ретранслятор запускается сам при первом включении тетеринга и закрывается при
выходе из программы.

- **Обновить adb** проверяет на сайте Google, есть ли более новая версия adb, и если есть —
  скачивает и устанавливает её. Перед обновлением нужно остановить тетеринг на всех
  телефонах. Если adb был установлен в системе, после обновления программа использует
  свою обновлённую копию.
- **Открыть папку инструментов** открывает папку, где хранятся gnirehtet и adb.
- **Проверить процессы** ищет процессы gnirehtet, оставшиеся от предыдущих сеансов
  (например, после аварийного закрытия), и другие копии программы, показывает их список с
  PID и командой и закрывает выбранные. Ретранслятор, который используется сейчас, в список
  не попадает. Та же проверка выполняется автоматически при запуске, а найденное
  сообщается в консоли. Кроме того, программу нельзя открыть дважды: повторный запуск
  выводит на передний план уже открытое окно.

### Подключённые устройства
Список телефонов, обнаруженных adb; обновляется каждые 2 секунды.

| Столбец | Значение |
|---|---|
| Устройство | Модель телефона |
| Серийный номер | Идентификатор, который использует adb |
| Состояние ADB | *Готов*, *Не авторизован*, *Не в сети*, *Нет прав USB* |
| Тетеринг | *Выключен*, идёт операция, *Активен* или *Ошибка* с причиной |
| Скорость | Текущая загрузка ↓ и отдача ↑ телефона |
| Трафик | Сколько данных получено (↓) и отправлено (↑) с момента включения тетеринга |

Скорость и трафик считываются прямо с телефона, с VPN-интерфейса gnirehtet: если цифры
меняются, **сеть действительно работает**. Если примерно через двадцать секунд трафик всё
ещё нулевой, в столбце Тетеринг появится *трафика пока нет*; если VPN вообще не активен —
*VPN на телефоне не активен?*, обычно потому, что запрос VPN не был подтверждён.

Кнопки:

- **Включить тетеринг**: проверяет, установлено ли приложение на телефоне (при
  необходимости устанавливает), запускает ретранслятор и включает подключение.
- **Остановить**: отключает подключение на выбранном телефоне.
- **Восстановить туннель**: заново создаёт связь между телефоном и компьютером, ничего не
  останавливая. Помогает, если сеть зависла после переподключения кабеля.
- **Двойной щелчок** по строке: включает или выключает тетеринг этого телефона.

Можно подключить **несколько телефонов одновременно**: каждый управляется своей строкой.

### Автозапуск
Если отмечен флажок **Автозапуск**, тетеринг включается сам на каждом подключённом
телефоне. Выбор запоминается.

Независимо от автозапуска, если отключить активный телефон, программа снова включит
тетеринг, когда вы его подключите.

### Консоль
Журнал всего происходящего: выполненные команды (синим), сообщения ретранслятора
(серым), успешные операции (зелёным), предупреждения (оранжевым) и ошибки (красным).
**Копировать всё** копирует журнал в буфер обмена — пригодится, если нужна помощь;
**Очистить** очищает его.

## Значок и уведомления

При закрытии окна программа **не завершается**: она остаётся в области уведомлений,
рядом с часами, и тетеринг продолжает работать.

- **Серый** значок: ни один телефон не подключён.
- **Зелёный** значок: хотя бы один телефон пользуется сетью компьютера.
- **Красный** значок: произошла ошибка.

При наведении на значок видно, сколько телефонов в тетеринге и общую скорость. Щелчок
показывает или скрывает окно. По правой кнопке: *Показать окно*, *Автозапуск*,
*Остановить всё* и **Выход**. Чтобы действительно закрыть программу, используйте
**Выход** — в меню значка или в меню *Файл*.

Программа показывает **уведомление**, когда телефон подключается или отключается, когда
тетеринг становится активным и когда возникает ошибка. Уведомления можно отключить в
Настройках.

## Настройки

Меню *Файл → Настройки* или кнопка **Настройки…**:

- **Путь к gnirehtet / adb**: оставьте пустым для автоматического поиска или укажите
  конкретный исполняемый файл.
- **Порт ретранслятора**: по умолчанию 31416. Меняйте, только если он занят.
- **DNS-серверы**: например `1.1.1.1,8.8.8.8`. Пусто — значения по умолчанию.
- **Язык**: итальянский, английский или русский (также через меню *Язык*). При первом
  запуске используется язык системы. Смена языка требует перезапуска, который программа
  сразу предлагает выполнить.
- **Показывать уведомления**: включает или выключает уведомления.
- **Останавливать тетеринг на телефонах при выходе**: рекомендуется, иначе VPN на
  телефоне остаётся включённым, но трафик не идёт.
- **Запускать свёрнутым в область уведомлений**: программа стартует без показа окна.

Изменения порта и DNS вступают в силу при следующем запуске тетеринга.

## Командная строка

```
python pupovina.py            обычный запуск
python pupovina.py --hidden   запуск сразу в области уведомлений
```

Параметр `--hidden` работает и с исполняемым файлом, и с AppImage.

## Решение проблем

**Телефон не появляется в списке**
Проверьте, что отладка по USB включена и кабель передаёт данные. На некоторых телефонах
нужно выбрать режим USB *Передача файлов*.

**Состояние «Не авторизован»**
Разблокируйте телефон и подтвердите запрос отладки по USB. Если запрос не появляется,
в *Параметрах разработчика* выберите *Отозвать авторизацию отладки по USB* и
переподключите кабель.

**Состояние «Нет прав USB» (только Linux)**
Не хватает правил udev для Android: установите `android-sdk-platform-tools-common`
(Debian/Ubuntu) или `android-udev-rules` (Arch, Fedora) и переподключите кабель.

**«Ретранслятор не запущен» или «порт 31416 занят»**
Порт уже использует другая программа. Если это оставшийся gnirehtet, программа сама
закроет его при запуске; можно также нажать **Проверить процессы**. Если это другая
программа, закройте её или смените порт в Настройках.

**Тетеринг «Активен», но интернета на телефоне нет**
Посмотрите на столбцы Скорость и Трафик. Если видно *VPN на телефоне не активен?*,
разблокируйте телефон и подтвердите запрос VPN. Если VPN активен, но трафик нулевой,
проверьте, что компьютер подключён к интернету, затем нажмите **Восстановить туннель**
или **Остановить** и снова **Включить**.

**Брандмауэр Windows**
При первом запуске ретранслятора Windows может спросить, разрешить ли gnirehtet доступ к
сети: разрешите хотя бы для частных сетей.

**Windows SmartScreen**
Исполняемый файл не подписан цифровой подписью, поэтому при первом запуске Windows может
показать *Система Windows защитила ваш компьютер*: выберите *Подробнее → Выполнить в
любом случае*.

## Конфиденциальность

Программа не собирает и не отправляет никаких данных. Она выходит в интернет, только
когда вы нажимаете **Скачать** или **Обновить adb**, чтобы загрузить gnirehtet с GitHub и
adb с сайта Google. Настройки хранятся на вашем компьютере.

## Благодарности

{app} — © 2026 {author}.

Основано на [gnirehtet](https://github.com/Genymobile/gnirehtet) от Genymobile,
распространяется по лицензии Apache 2.0. adb входит в состав Android SDK Platform Tools
от Google.
"""


def manual_text(tools_dir: str | None = None, lang: str | None = None) -> str:
    return MANUAL[lang or LANG].format(
        app=APP_NAME, ver=__version__, author=__author__, gv=GNIREHTET_VERSION,
        folder=tools_dir or str(TOOLS_DIR))


# ---------------------------------------------------------------------------
# Finestra principale
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("GnirehtetGUI", "GnirehtetGUI")
        self.bridge = Bridge()
        self.relay = Relay(self.bridge)
        self.jobs = ThreadPoolExecutor(max_workers=1)    # comandi sui dispositivi, in sequenza
        self.poller = ThreadPoolExecutor(max_workers=1)  # adb devices
        self.stats_pool = ThreadPoolExecutor(max_workers=2)  # letture del traffico
        self.dl = ThreadPoolExecutor(max_workers=1)      # download e controlli

        self.gnirehtet: Path | None = None
        self.adb: Path | None = None
        self.adb_ver: tuple[int, ...] | None = None
        self.devices: dict[str, tuple[str, str]] = {}
        self.tether: dict[str, tuple[str, str]] = {}    # seriale -> (stato, dettaglio)
        self.traffic: dict[str, dict] = {}              # seriale -> contatori
        self._stats_inflight: set[str] = set()
        self.reconnect: set[str] = set()                # attivi scollegati da riattivare
        self._polling = False
        self._first_poll = True
        self._quitting = False
        self._tray_hint_shown = False

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(make_icon(ICON_COLORS["idle"]))
        self.resize(940, 640)
        self._build_ui()
        self._build_tray()

        b = self.bridge
        b.log.connect(self.log)
        b.devices.connect(self._on_devices)
        b.status.connect(self._on_status)
        b.relay_state.connect(self._on_relay_state)
        b.tools_changed.connect(self.refresh_tools)
        b.stats.connect(self._on_stats)
        b.adb_version.connect(self._on_adb_version)
        b.update_check.connect(self._on_update_check)
        b.procs.connect(self._on_procs)

        self.refresh_tools()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(POLL_MS)
        QTimer.singleShot(100, self.poll)
        QTimer.singleShot(1500, lambda: self.check_processes(manual=False))

    # ----------------------------------------------------------------- UI --
    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)

        tools = QGroupBox(T("tools"))
        tl = QFormLayout(tools)
        self.lbl_gn = QLabel()
        self.btn_dl_gn = QPushButton(T("dl_gn", v=GNIREHTET_VERSION))
        self.btn_dl_gn.clicked.connect(lambda: self.download("gnirehtet"))
        tl.addRow("gnirehtet:", self._row(self.lbl_gn, self.btn_dl_gn))
        self.lbl_adb = QLabel()
        self.btn_dl_adb = QPushButton(T("dl_adb"))
        self.btn_dl_adb.clicked.connect(lambda: self.download("adb"))
        self.btn_upd_adb = QPushButton(T("upd_adb"))
        self.btn_upd_adb.clicked.connect(self.check_adb_update)
        tl.addRow("adb:", self._row(self.lbl_adb, self.btn_dl_adb, self.btn_upd_adb))
        self.lbl_relay = QLabel()
        self.btn_procs = QPushButton(T("btn_procs"))
        self.btn_procs.setToolTip(T("procs_tip"))
        self.btn_procs.clicked.connect(lambda: self.check_processes(manual=True))
        tl.addRow(T("relay"), self._row(self.lbl_relay, self.btn_procs))
        btn_folder = QPushButton(T("open_folder"))
        btn_folder.clicked.connect(self.open_tools_folder)
        lbl_dir = QLabel(html.escape(str(TOOLS_DIR)))
        lbl_dir.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        tl.addRow(T("folder"), self._row(lbl_dir, btn_folder))
        root.addWidget(tools)

        splitter = QSplitter(Qt.Orientation.Vertical)

        dev_box = QGroupBox(T("devices"))
        dl = QVBoxLayout(dev_box)
        cols = [T(k) for k in ("col_device", "col_serial", "col_adb", "col_tether",
                                "col_speed", "col_traffic")]
        self.table = QTableWidget(0, len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        hh = self.table.horizontalHeader()
        for i in range(len(cols)):
            hh.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self.table.cellDoubleClicked.connect(lambda *_: self._toggle_selected())
        dl.addWidget(self.table)
        self.lbl_empty = QLabel(T("no_devices"))
        self.lbl_empty.setWordWrap(True)
        dl.addWidget(self.lbl_empty)

        bl = QHBoxLayout()
        self.btn_start = QPushButton(T("btn_start"))
        self.btn_start.clicked.connect(lambda: self._with_selected(self.start_device))
        self.btn_stop = QPushButton(T("btn_stop"))
        self.btn_stop.clicked.connect(lambda: self._with_selected(self.stop_device))
        self.btn_tunnel = QPushButton(T("btn_tunnel"))
        self.btn_tunnel.setToolTip(T("tunnel_tip"))
        self.btn_tunnel.clicked.connect(lambda: self._with_selected(self.reset_tunnel))
        self.chk_autorun = QCheckBox(T("autorun"))
        self.chk_autorun.setChecked(self.settings.value("autorun", False, bool))
        self.chk_autorun.toggled.connect(self.set_autorun)
        btn_settings = QPushButton(T("btn_settings"))
        btn_settings.clicked.connect(self.open_settings)
        for w in (self.btn_start, self.btn_stop, self.btn_tunnel):
            bl.addWidget(w)
        bl.addStretch()
        bl.addWidget(self.chk_autorun)
        bl.addWidget(btn_settings)
        dl.addLayout(bl)
        splitter.addWidget(dev_box)

        log_box = QGroupBox(T("console"))
        ll = QVBoxLayout(log_box)
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(3000)
        font = self.console.font()
        font.setFamily("Consolas" if IS_WIN else "Monospace")
        font.setStyleHint(font.StyleHint.Monospace)
        self.console.setFont(font)
        ll.addWidget(self.console)
        cl = QHBoxLayout()
        cl.addStretch()
        b_copy = QPushButton(T("copy_all"))
        b_copy.clicked.connect(lambda: QApplication.clipboard().setText(self.console.toPlainText()))
        b_clear = QPushButton(T("clear"))
        b_clear.clicked.connect(self.console.clear)
        cl.addWidget(b_copy)
        cl.addWidget(b_clear)
        ll.addLayout(cl)
        splitter.addWidget(log_box)
        splitter.setSizes([320, 220])

        root.addWidget(splitter)
        self.setCentralWidget(central)
        self._build_menu()
        sig = QLabel(f"{APP_NAME} {__version__} — © 2026 {__author__}")
        sig.setStyleSheet("color:#7a828e; padding:0 6px;")
        self.statusBar().addPermanentWidget(sig)
        self._on_relay_state(False)
        self._update_buttons()

    def _build_menu(self) -> None:
        mb = self.menuBar()
        m_file = mb.addMenu(T("m_file"))
        m_file.addAction(T("m_settings")).triggered.connect(self.open_settings)
        m_file.addAction(T("open_folder")).triggered.connect(self.open_tools_folder)
        m_file.addAction(T("upd_adb")).triggered.connect(self.check_adb_update)
        m_file.addAction(T("btn_procs")).triggered.connect(lambda: self.check_processes(manual=True))
        m_file.addSeparator()
        m_file.addAction(T("m_quit")).triggered.connect(self.quit_app)

        m_lang = mb.addMenu(T("m_lang"))
        group = QActionGroup(self)
        for code, name in LANGUAGES.items():
            a = QAction(name, self, checkable=True)
            a.setChecked(code == LANG)
            a.triggered.connect(lambda _=False, c=code: self.change_language(c))
            group.addAction(a)
            m_lang.addAction(a)

        m_help = mb.addMenu(T("m_help"))
        a = m_help.addAction(T("m_manual"))
        a.setShortcut("F1")
        a.triggered.connect(self.show_manual)
        m_help.addAction(T("m_about", app=APP_NAME)).triggered.connect(self.show_about)

    @staticmethod
    def _row(*widgets) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        for x in widgets:
            h.addWidget(x)
        h.addStretch()
        return w

    def _build_tray(self) -> None:
        self.tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(make_icon(ICON_COLORS["idle"]), self)
        self.tray.setToolTip(APP_NAME)
        menu = QMenu()
        menu.addAction(T("tray_show")).triggered.connect(self.show_window)
        self.act_autorun = QAction(T("tray_autorun"), self, checkable=True)
        self.act_autorun.setChecked(self.chk_autorun.isChecked())
        self.act_autorun.toggled.connect(self.chk_autorun.setChecked)
        menu.addAction(self.act_autorun)
        menu.addSeparator()
        menu.addAction(T("tray_stop_all")).triggered.connect(self.stop_all)
        menu.addAction(T("m_quit")).triggered.connect(self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self._tray_menu = menu
        self.tray.show()

    def _tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible() and not self.isMinimized():
                self.hide()
            else:
                self.show_window()

    def show_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def notify(self, title: str, message: str, error: bool = False) -> None:
        if not self.tray or not self.settings.value("notifications", True, bool):
            return
        icon = (QSystemTrayIcon.MessageIcon.Warning if error
                else QSystemTrayIcon.MessageIcon.Information)
        self.tray.showMessage(title, message, icon, 4000)

    def name_of(self, serial: str) -> str:
        model = self.devices.get(serial, ("", ""))[1]
        return model or serial

    # ----------------------------------------------------- Aiuto e lingua --
    def show_manual(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle(f"{T('m_manual')} — {APP_NAME}")
        lay = QVBoxLayout(dlg)
        tb = QTextBrowser()
        tb.setOpenExternalLinks(True)
        tb.setMarkdown(manual_text())
        lay.addWidget(tb)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        dlg.resize(780, 660)
        dlg.exec()

    def show_about(self) -> None:
        QMessageBox.about(self, T("m_about", app=APP_NAME),
                          T("about", app=APP_NAME, ver=__version__, author=__author__))

    def change_language(self, code: str) -> None:
        if code == LANG:
            return
        self.settings.setValue("language", code)
        self.settings.sync()
        ans = QMessageBox.question(self, T("lang_title"), T("lang_restart"))
        if ans == QMessageBox.StandardButton.Yes:
            self.restart_app()

    def restart_app(self) -> None:
        if os.environ.get("APPIMAGE"):
            program, args = os.environ["APPIMAGE"], sys.argv[1:]
        elif getattr(sys, "frozen", False):
            program, args = sys.executable, sys.argv[1:]
        else:
            program, args = sys.executable, [str(Path(__file__).resolve()), *sys.argv[1:]]
        self.quit_app()
        QProcess.startDetached(program, args)

    def open_tools_folder(self) -> None:
        TOOLS_DIR.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(TOOLS_DIR)))

    # ------------------------------------------------------------- Console --
    def log(self, level: str, text: str) -> None:
        colors = {"info": None, "ok": "#2e9d57", "warn": "#c77c00", "err": "#d64545",
                  "relay": "#7a828e", "cmd": "#3a7bd5"}
        ts = datetime.now().strftime("%H:%M:%S")
        prefix = {"relay": "relay │ ", "cmd": "$ "}.get(level, "")
        for line in text.splitlines() or [""]:
            body = html.escape(prefix + line)
            c = colors.get(level)
            if c:
                body = f'<span style="color:{c}">{body}</span>'
            self.console.appendHtml(f'<span style="color:#9aa0a6">{ts}</span>  {body}')

    # ------------------------------------------------------------ Strumenti --
    def refresh_tools(self) -> None:
        s = self.settings
        self.gnirehtet = locate_gnirehtet(s.value("gnirehtet_path", "", str),
                                          s.value("found_gnirehtet", "", str))
        self.adb = locate_adb(s.value("adb_path", "", str),
                              s.value("found_adb", "", str), self.gnirehtet)
        # ricorda dove sono, così al prossimo avvio li ritrova subito
        if self.gnirehtet:
            s.setValue("found_gnirehtet", str(self.gnirehtet))
        if self.adb:
            s.setValue("found_adb", str(self.adb))
        s.sync()
        pk = platform_key()
        self.lbl_gn.setText(self._path_html(self.gnirehtet))
        self.btn_dl_gn.setVisible(self.gnirehtet is None and pk is not None)
        self.btn_dl_gn.setEnabled(True)
        self.adb_ver = None
        self.lbl_adb.setText(self._path_html(self.adb))
        self.btn_dl_adb.setVisible(self.adb is None and pk is not None)
        self.btn_dl_adb.setEnabled(True)
        self.btn_upd_adb.setVisible(self.adb is not None and pk is not None)
        self.btn_upd_adb.setEnabled(True)
        if self.adb:
            self.dl.submit(self._adb_version_job, self.adb)
        self._update_buttons()

    @staticmethod
    def _path_html(path: Path | None, extra: str = "") -> str:
        if not path:
            return f'<span style="color:#d64545">{T("not_found")}</span>'
        tail = f' <span style="color:#7a828e">({html.escape(extra)})</span>' if extra else ""
        return f'<span style="color:#2e9d57">✔</span> {html.escape(str(path))}{tail}'

    def _adb_version_job(self, adb: Path) -> None:
        _, out = run_cmd([adb, "version"], env=self.env(), timeout=15)
        self.bridge.safe_emit("adb_version", parse_adb_version(out))

    def _on_adb_version(self, ver) -> None:
        self.adb_ver = ver
        if self.adb:
            self.lbl_adb.setText(self._path_html(self.adb, T("version", v=vstr(ver))))

    def tools_ok(self, quiet: bool = False) -> bool:
        if self.gnirehtet and self.adb:
            return True
        if not quiet:
            self.log("err", T("err_tools"))
        return False

    def env(self) -> dict:
        e = os.environ.copy()
        if self.adb:
            e["ADB"] = str(self.adb)
            e["PATH"] = str(self.adb.parent) + os.pathsep + e.get("PATH", "")
        if self.gnirehtet:
            apk = self.gnirehtet.parent / "gnirehtet.apk"
            if apk.is_file():
                e["GNIREHTET_APK"] = str(apk)
        return e

    def download(self, what: str) -> None:
        pk = platform_key()
        if pk is None:
            self.log("err", T("err_platform"))
            return
        url, sha = DOWNLOADS[what][pk]
        # dopo il download va usata la copia appena scaricata
        self.settings.remove(f"found_{what}")
        for btn in (self.btn_dl_gn, self.btn_dl_adb, self.btn_upd_adb):
            btn.setEnabled(False)
        self.dl.submit(self._download_job, what, url, sha, self.adb if what == "adb" else None)

    def _download_job(self, what: str, url: str, sha: str | None, old_adb: Path | None) -> None:
        b = self.bridge
        b.safe_emit("log", "info", T("log_dl", url=url))
        try:
            TOOLS_DIR.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory() as td:
                zp = Path(td) / "package.zip"
                h = hashlib.sha256()
                req = urllib.request.Request(url, headers={"User-Agent": APP_NAME})
                with urllib.request.urlopen(req, timeout=60) as r, open(zp, "wb") as f:
                    total = int(r.headers.get("Content-Length") or 0)
                    done, last = 0, -1
                    while chunk := r.read(65536):
                        f.write(chunk)
                        h.update(chunk)
                        done += len(chunk)
                        if total:
                            pct = done * 100 // total
                            if pct // 25 > last:
                                last = pct // 25
                                b.safe_emit("log", "info", f"  {pct}%  ({fmt_bytes(done)})")
                if sha and h.hexdigest() != sha:
                    raise RuntimeError(T("err_sha"))
                if sha:
                    b.safe_emit("log", "ok", T("log_sha_ok"))
                if what == "adb" and old_adb:
                    # adb in esecuzione blocca i file (soprattutto su Windows)
                    run_cmd([old_adb, "kill-server"], timeout=15)
                    time.sleep(0.5)
                with zipfile.ZipFile(zp) as z:
                    z.extractall(TOOLS_DIR)
            exe = find_in_tree(TOOLS_DIR, ("gnirehtet" if what == "gnirehtet" else "adb") + EXE)
            if exe:
                make_executable(exe)
            b.safe_emit("log", "ok", T("log_installed", what=what, dir=TOOLS_DIR))
            if what == "adb" and IS_LINUX:
                b.safe_emit("log", "info", T("log_udev"))
        except Exception as e:  # noqa: BLE001
            b.safe_emit("log", "err", T("err_dl", what=what, e=e))
        finally:
            b.safe_emit("tools_changed")

    # ------------------------------------------------------ Aggiorna adb --
    def check_adb_update(self) -> None:
        if platform_key() is None:
            self.log("err", T("err_platform"))
            return
        if any(st in (ST_ACTIVE, ST_BUSY) for st, _ in self.tether.values()):
            QMessageBox.information(self, T("upd_title"), T("upd_busy"))
            return
        self.log("info", T("upd_checking"))
        self.btn_upd_adb.setEnabled(False)
        self.dl.submit(self._update_check_job, self.adb, self.env())

    def _update_check_job(self, adb: Path | None, env: dict) -> None:
        cur = None
        if adb:
            _, out = run_cmd([adb, "version"], env=env, timeout=15)
            cur = parse_adb_version(out)
        latest, err = None, ""
        for url in SDK_REPOSITORY_URLS:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": APP_NAME})
                with urllib.request.urlopen(req, timeout=30) as r:
                    latest = parse_latest_platform_tools(r.read())
                if latest:
                    break
            except Exception as e:  # noqa: BLE001
                err = str(e)
        if not latest and not err:
            err = "platform-tools?"
        self.bridge.safe_emit("update_check", cur, latest, err)

    def _on_update_check(self, cur, latest, err: str) -> None:
        self.btn_upd_adb.setEnabled(True)
        if latest:
            self.log("info", T("upd_latest_log", cur=vstr(cur), latest=vstr(latest)))
            if cur and tuple(cur) >= tuple(latest):
                QMessageBox.information(self, T("upd_title"), T("upd_ok", cur=vstr(cur)))
                return
            question = T("upd_available", latest=vstr(latest), cur=vstr(cur))
        else:
            self.log("warn", T("upd_unknown", e=err).splitlines()[0])
            question = T("upd_unknown", e=err)
        ans = QMessageBox.question(self, T("upd_title"), question)
        if ans == QMessageBox.StandardButton.Yes:
            self.download("adb")

    # ------------------------------------------------- Processi rimasti --
    def _own_pids(self) -> set[int]:
        pids = set()
        if self.relay.running() and self.relay.proc is not None:
            pids.add(self.relay.proc.pid)
        return pids

    def check_processes(self, manual: bool) -> None:
        if manual:
            self.log("info", T("procs_checking"))
            self.btn_procs.setEnabled(False)
        self.dl.submit(self._procs_job, self._own_pids(), manual)

    def _procs_job(self, exclude: set[int], manual: bool) -> None:
        try:
            procs, err = find_leftover_processes(exclude), ""
        except Exception as e:  # noqa: BLE001
            procs, err = [], str(e)
        self.bridge.safe_emit("procs", procs, manual, err)

    def _on_procs(self, procs, manual: bool, err: str) -> None:
        self.btn_procs.setEnabled(True)
        # il relay potrebbe essere partito nel frattempo: non elencarlo
        procs = [p for p in procs if p[0] not in self._own_pids()]
        if err:
            if manual:
                self.log("err", T("procs_error", e=err))
            return
        if not manual:
            if procs:
                self.log("warn", T("procs_found", n=len(procs)))
            return
        if not procs:
            self.log("ok", T("procs_none"))
            QMessageBox.information(self, T("procs_title"), T("procs_none"))
            return
        dlg = ProcessesDialog(procs, self)
        if not dlg.exec():
            return
        killed = 0
        for pid in dlg.selected_pids():
            e = kill_process(pid)
            if e:
                self.log("err", T("procs_kill_fail", pid=pid, e=e))
            else:
                killed += 1
        self.log("ok", T("procs_killed", n=killed))

    # ---------------------------------------------------------- Dispositivi --
    def poll(self) -> None:
        if self._quitting:
            return
        if not self.adb:
            self._on_devices({})
            return
        if not self._polling:
            self._polling = True
            self.poller.submit(self._poll_job, self.adb, self.env())
        env = None
        for serial, (st, _) in self.tether.items():
            if st == ST_ACTIVE and serial not in self._stats_inflight:
                env = env or self.env()
                self._stats_inflight.add(serial)
                self.stats_pool.submit(self._stats_job, serial, self.adb, env)

    def _poll_job(self, adb: Path, env: dict) -> None:
        try:
            code, out = run_cmd([adb, "devices", "-l"], env=env, timeout=15)
            if code == 0:
                self.bridge.safe_emit("devices", parse_adb_devices(out))
        finally:
            self._polling = False

    def _stats_job(self, serial: str, adb: Path, env: dict) -> None:
        code, out = run_cmd([adb, "-s", serial, "shell", "cat", "/proc/net/dev"],
                            env=env, timeout=10)
        counters = parse_net_dev(out) if code == 0 else None
        self.bridge.safe_emit("stats", serial, counters, time.monotonic())

    def _on_stats(self, serial: str, counters, t: float) -> None:
        self._stats_inflight.discard(serial)
        tr = self.traffic.get(serial)
        if tr is None or self.tether.get(serial, ("", ""))[0] != ST_ACTIVE:
            return
        if counters is None:
            tr["vpn"] = False
        else:
            rx, tx = counters
            tr["vpn"] = True
            last = tr.get("last")
            if last is None or rx < last[0] or tx < last[1]:   # primo dato o contatori azzerati
                tr["base"] = (rx, tx)
                tr["rate"] = (0.0, 0.0)
            else:
                dt = max(t - last[2], 1e-3)
                tr["rate"] = ((rx - last[0]) / dt, (tx - last[1]) / dt)
            tr["last"] = (rx, tx, t)
        self._render_table()

    def _on_devices(self, devices: dict) -> None:
        old = self.devices
        self.devices = devices
        first = self._first_poll
        self._first_poll = False

        for serial in set(old) - set(devices):
            name = old[serial][1] or serial
            st, _ = self.tether.get(serial, (ST_IDLE, ""))
            if st in (ST_ACTIVE, ST_BUSY):
                self.reconnect.add(serial)
                self.log("warn", T("log_will_reconnect", name=name))
            else:
                self.log("info", T("log_disconnected", name=name))
            self.notify(T("n_disconnected"), name)
            self.tether.pop(serial, None)
            self.traffic.pop(serial, None)

        for serial, (state, model) in devices.items():
            ready = state == "device"
            was_ready = old.get(serial, ("", ""))[0] == "device"
            name = model or serial
            if serial not in old:
                adb_state = T(f"adb_{state}") if f"adb_{state}" in S else state
                self.log("info", T("log_connected", name=name, state=adb_state))
                if not first:
                    self.notify(T("n_connected"), f"{name} — {adb_state}")
            if ready and not was_ready:
                if serial in self.reconnect:
                    self.reconnect.discard(serial)
                    self.start_device(serial)
                elif self.chk_autorun.isChecked():
                    self.start_device(serial)

        self._render_table()

    def _traffic_cells(self, serial: str) -> tuple[str, str, str]:
        """(velocità, traffico, avviso per la colonna Tethering)."""
        tr = self.traffic.get(serial)
        if not tr:
            return "", "", ""
        age = time.monotonic() - tr["since"]
        if not tr.get("vpn") or "last" not in tr:
            hint = T("vpn_off") if age > NO_TRAFFIC_HINT_S and tr.get("vpn") is False else ""
            return "—", "—", hint
        rx, tx, _ = tr["last"]
        down, up = rx - tr["base"][0], tx - tr["base"][1]
        rdown, rup = tr["rate"]
        hint = T("no_traffic") if age > NO_TRAFFIC_HINT_S and down + up == 0 else ""
        return (f"↓ {fmt_rate(rdown)}   ↑ {fmt_rate(rup)}",
                f"↓ {fmt_bytes(down)}   ↑ {fmt_bytes(up)}", hint)

    def _render_table(self) -> None:
        selected = self.selected_serial()
        self.table.setRowCount(len(self.devices))
        colors = {ST_ACTIVE: "#2e9d57", ST_ERROR: "#d64545", ST_BUSY: "#c77c00"}
        for row, (serial, (state, model)) in enumerate(sorted(self.devices.items())):
            st, detail = self.tether.get(serial, (ST_IDLE, ""))
            speed, traffic, hint = self._traffic_cells(serial) if st == ST_ACTIVE else ("", "", "")
            if st == ST_ACTIVE:
                label = T("st_active") + (f" — {detail or hint}" if (detail or hint) else "")
            elif st == ST_BUSY:
                label = detail or T("st_busy")
            elif st == ST_ERROR:
                label = T("st_error") + (f": {detail}" if detail else "")
            else:
                label = T("st_idle")
            adb_state = T(f"adb_{state}") if f"adb_{state}" in S else state
            values = [model or "—", serial, adb_state, label, speed, traffic]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                if col == 3 and st in colors:
                    color = "#c77c00" if (st == ST_ACTIVE and hint) else colors[st]
                    item.setForeground(QColor(color))
                if col == 2 and state != "device":
                    item.setForeground(QColor("#c77c00"))
                self.table.setItem(row, col, item)
            if serial == selected:
                self.table.selectRow(row)
        if selected is None and self.devices and self.table.rowCount():
            self.table.selectRow(0)
        self.lbl_empty.setVisible(not self.devices)
        self._update_buttons()
        self._update_tray_icon()

    def selected_serial(self) -> str | None:
        sm = self.table.selectionModel()
        rows = sm.selectedRows() if sm else []
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 1)
        return item.text() if item else None

    def _with_selected(self, fn) -> None:
        s = self.selected_serial()
        if s:
            fn(s)

    def _toggle_selected(self) -> None:
        s = self.selected_serial()
        if not s:
            return
        if self.tether.get(s, (ST_IDLE, ""))[0] == ST_ACTIVE:
            self.stop_device(s)
        else:
            self.start_device(s)

    def _update_buttons(self) -> None:
        s = self.selected_serial()
        ready = bool(s) and self.devices.get(s, ("", ""))[0] == "device" and self.tools_ok(True)
        st = self.tether.get(s, (ST_IDLE, ""))[0] if s else ST_IDLE
        self.btn_start.setEnabled(ready and st in (ST_IDLE, ST_ERROR))
        self.btn_stop.setEnabled(ready and st in (ST_ACTIVE, ST_ERROR))
        self.btn_tunnel.setEnabled(ready and st == ST_ACTIVE)

    def _update_tray_icon(self) -> None:
        states = [v[0] for v in self.tether.values()]
        key = "active" if ST_ACTIVE in states else ("error" if ST_ERROR in states else "idle")
        icon = make_icon(ICON_COLORS[key])
        self.setWindowIcon(icon)
        if self.tray:
            self.tray.setIcon(icon)
            n = states.count(ST_ACTIVE)
            if n:
                down = sum(tr.get("rate", (0, 0))[0] for tr in self.traffic.values())
                up = sum(tr.get("rate", (0, 0))[1] for tr in self.traffic.values())
                tip = f"{APP_NAME}\n" + T("tray_tip", n=n, down=fmt_rate(down), up=fmt_rate(up))
            else:
                tip = APP_NAME
            self.tray.setToolTip(tip)

    # ------------------------------------------------------------ Comandi --
    def _gn_opts(self) -> list[str]:
        opts = []
        dns = self.settings.value("dns", "", str)
        if dns:
            opts += ["-d", dns]
        port = int(self.settings.value("port", DEFAULT_PORT))
        if port != DEFAULT_PORT:
            opts += ["-p", str(port)]
        return opts

    def start_device(self, serial: str) -> None:
        if not self.tools_ok():
            return
        if self.tether.get(serial, (ST_IDLE, ""))[0] in (ST_BUSY, ST_ACTIVE):
            return
        self._on_status(serial, ST_BUSY, T("queued"))
        self.jobs.submit(self._start_job, serial, self.name_of(serial), self.gnirehtet, self.adb,
                         self.env(), int(self.settings.value("port", DEFAULT_PORT)),
                         self._gn_opts())

    def _start_job(self, serial, name, gn: Path, adb: Path, env, port, opts) -> None:
        b = self.bridge
        try:
            if not self.relay.start(gn, env, port):
                b.safe_emit("status", serial, ST_ERROR, self.relay.last_error or T("err_relay"))
                return
            b.safe_emit("status", serial, ST_BUSY, T("checking_app"))
            _, out = run_cmd([adb, "-s", serial, "shell", "pm", "path", PACKAGE], env=env, timeout=20)
            if "package:" not in out:
                b.safe_emit("status", serial, ST_BUSY, T("installing_app"))
                args = [gn, "install", serial]
                b.safe_emit("log", "cmd", fmt_cmd(args))
                code, out = run_cmd(args, env=env, cwd=gn.parent, timeout=180)
                if out:
                    b.safe_emit("log", "info", out)
                if code != 0:
                    b.safe_emit("status", serial, ST_ERROR, T("err_install"))
                    return
                b.safe_emit("log", "warn", T("log_vpn_first"))
            b.safe_emit("status", serial, ST_BUSY, T("starting"))
            args = [gn, "start", serial, *opts]
            b.safe_emit("log", "cmd", fmt_cmd(args))
            code, out = run_cmd(args, env=env, cwd=gn.parent, timeout=60)
            if out:
                b.safe_emit("log", "info", out)
            if code == 0:
                b.safe_emit("status", serial, ST_ACTIVE, "")
                b.safe_emit("log", "ok", T("log_active", name=name))
            else:
                b.safe_emit("status", serial, ST_ERROR, T("err_code", code=code))
        except Exception as e:  # noqa: BLE001
            b.safe_emit("status", serial, ST_ERROR, str(e))

    def stop_device(self, serial: str) -> None:
        if not self.tools_ok():
            return
        self.reconnect.discard(serial)
        self._on_status(serial, ST_BUSY, T("stopping"))
        self.jobs.submit(self._simple_job, serial, "stop", ST_IDLE)

    def reset_tunnel(self, serial: str) -> None:
        if not self.tools_ok():
            return
        self._on_status(serial, ST_BUSY, T("resetting"))
        self.jobs.submit(self._simple_job, serial, "tunnel", ST_ACTIVE)

    def _simple_job(self, serial: str, command: str, success_state: str) -> None:
        gn, env = self.gnirehtet, self.env()
        assert gn is not None
        args = [gn, command, serial]
        if command == "tunnel":
            port = int(self.settings.value("port", DEFAULT_PORT))
            if port != DEFAULT_PORT:
                args += ["-p", str(port)]
        self.bridge.safe_emit("log", "cmd", fmt_cmd(args))
        code, out = run_cmd(args, env=env, cwd=gn.parent, timeout=60)
        if out:
            self.bridge.safe_emit("log", "info", out)
        if code == 0:
            self.bridge.safe_emit("status", serial, success_state, "")
        else:
            self.bridge.safe_emit("status", serial, ST_ERROR, T("err_cmd", cmd=command, code=code))

    def stop_all(self) -> None:
        self.reconnect.clear()
        for serial, (st, _) in list(self.tether.items()):
            if st in (ST_ACTIVE, ST_ERROR) and serial in self.devices:
                self.stop_device(serial)

    def set_autorun(self, on: bool) -> None:
        self.settings.setValue("autorun", on)
        if self.tray and self.act_autorun.isChecked() != on:
            self.act_autorun.setChecked(on)
        self.log("info", T("log_autorun_on") if on else T("log_autorun_off"))
        if on:
            for serial, (state, _) in self.devices.items():
                if state == "device" and self.tether.get(serial, (ST_IDLE, ""))[0] in (ST_IDLE, ST_ERROR):
                    self.start_device(serial)

    def _on_status(self, serial: str, state: str, detail: str) -> None:
        prev = self.tether.get(serial, (ST_IDLE, ""))[0]
        if serial in self.devices or state == ST_BUSY:
            self.tether[serial] = (state, detail)
        name = self.name_of(serial)
        if state == ST_ACTIVE and prev != ST_ACTIVE:
            self.traffic[serial] = {"since": time.monotonic(), "rate": (0.0, 0.0)}
            self.notify(T("n_active"), T("n_active_msg", name=name))
        elif state != ST_ACTIVE and state != ST_BUSY:
            self.traffic.pop(serial, None)
        if state == ST_ERROR:
            self.log("err", T("log_error", name=name, detail=detail))
            self.notify(T("n_error"), f"{name}: {detail}", error=True)
        self._render_table()

    def _on_relay_state(self, running: bool) -> None:
        if running:
            port = int(self.settings.value("port", DEFAULT_PORT))
            self.lbl_relay.setText(f'<span style="color:#2e9d57">{T("relay_on")}</span> '
                                   f'{T("relay_port", p=port)}')
        else:
            self.lbl_relay.setText(f'<span style="color:#8a919c">{T("relay_off")}</span> '
                                   f'{T("relay_off_note")}')
            if not self._quitting and getattr(self, "tether", None):
                for serial, (st, _) in list(self.tether.items()):
                    if st == ST_ACTIVE:
                        self._on_status(serial, ST_ERROR, T("relay_closed"))

    # ------------------------------------------------------- Impostazioni --
    def open_settings(self) -> None:
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec():
            self.refresh_tools()
            if self.relay.running():
                self.log("info", T("log_next_time"))
            if dlg.chosen_language() != LANG:
                self.change_language(dlg.chosen_language())

    # ------------------------------------------------------------- Uscita --
    def closeEvent(self, event) -> None:
        if self.tray and not self._quitting:
            event.ignore()
            self.hide()
            if not self._tray_hint_shown:
                self._tray_hint_shown = True
                self.tray.showMessage(APP_NAME, T("tray_hint"),
                                      QSystemTrayIcon.MessageIcon.Information, 3000)
            return
        self._shutdown()
        event.accept()

    def quit_app(self) -> None:
        self._quitting = True
        self._shutdown()
        QApplication.quit()

    def _shutdown(self) -> None:
        if getattr(self, "_shut", False):
            return
        self._shut = True
        self._quitting = True
        self.timer.stop()
        if self.settings.value("stop_on_exit", True, bool) and self.gnirehtet:
            env = self.env()
            for serial, (st, _) in list(self.tether.items()):
                if st == ST_ACTIVE and serial in self.devices:
                    run_cmd([self.gnirehtet, "stop", serial], env=env,
                            cwd=self.gnirehtet.parent, timeout=10)
        self.relay.stop()
        for ex in (self.jobs, self.poller, self.stats_pool, self.dl):
            ex.shutdown(wait=False, cancel_futures=True)
        if self.tray:
            self.tray.hide()
        server = getattr(self, "instance_server", None)
        if server is not None:
            server.close()


def instance_key() -> str:
    try:
        user = getpass.getuser()
    except Exception:  # noqa: BLE001
        user = "user"
    return f"GnirehtetGUI-{re.sub(r'[^A-Za-z0-9_]', '_', user)}"


def activate_running_instance() -> bool:
    """Se il programma è già aperto, gli chiede di mostrarsi e restituisce True."""
    sock = QLocalSocket()
    sock.connectToServer(instance_key())
    if not sock.waitForConnected(500):
        return False
    sock.write(b"show")
    sock.flush()
    sock.waitForBytesWritten(500)
    sock.disconnectFromServer()
    return True


def main() -> int:
    global LANG
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setWindowIcon(make_icon(ICON_COLORS["idle"]))
    LANG = detect_language(QSettings("GnirehtetGUI", "GnirehtetGUI").value("language", "", str))
    if activate_running_instance():
        return 0
    # traduce anche i pulsanti standard di Qt (OK, Annulla, Sì, No…)
    qt_tr = QTranslator(app)
    if qt_tr.load(f"qtbase_{LANG}", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(qt_tr)
    w = MainWindow()
    server = QLocalServer()
    QLocalServer.removeServer(instance_key())   # ripulisce un eventuale server rimasto da un crash
    if server.listen(instance_key()):
        server.newConnection.connect(
            lambda: (server.nextPendingConnection(), w.show_window()))
    w.instance_server = server
    app.setQuitOnLastWindowClosed(w.tray is None)
    hidden = w.tray is not None and (
        "--nascosto" in sys.argv or "--hidden" in sys.argv
        or w.settings.value("start_hidden", False, bool))
    if not hidden:
        w.show()
    w.log("info", T("log_ready", app=APP_NAME, ver=__version__, dir=TOOLS_DIR))
    if not w.tools_ok(quiet=True):
        w.log("warn", T("log_missing"))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
