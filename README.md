<p align="center"><img src="assets/icon.png" width="96" alt=""></p>

<h1 align="center">Gnirehtet GUI</h1>

<p align="center"><i>di / by / автор: Dmitrij Musella</i></p>

<p align="center">
<a href="#italiano">Italiano</a> · <a href="#english">English</a> · <a href="#русский">Русский</a>
</p>

---

## Italiano

Interfaccia grafica per [gnirehtet](https://github.com/Genymobile/gnirehtet):
il telefono Android usa la **connessione internet del computer tramite cavo USB**
(reverse tethering), senza root. Funziona su Windows e Linux.

**Funzioni**
- Scarica da sola gnirehtet (con verifica SHA-256) e adb, e li conserva sul computer.
- Elenco dei telefoni collegati, con **velocità e traffico in tempo reale** di ognuno.
- Avvio, arresto e ripristino del tunnel con un clic; più telefoni insieme.
- **Autorun**: attiva il tethering su ogni telefono che colleghi.
- Icona nell'area di notifica e **notifiche** per collegamento, scollegamento ed errori.
- **Aggiornamento di adb** con un pulsante.
- **Controlla processi**: trova e chiude i gnirehtet rimasti aperti e le copie doppie del programma.
- Interfaccia in **italiano, inglese e russo**.
- Console con il registro completo e **manuale utente** integrato (F1).

**Scaricare**: dalla pagina [Releases](../../releases) prendi `GnirehtetGUI.exe` (Windows)
oppure `GnirehtetGUI-x86_64.AppImage` (Linux). Non serve Python.

**Dal codice**: `pip install -r requirements.txt` e poi `python gnirehtet_gui.py`.

Manuale completo: [docs/MANUALE.md](docs/MANUALE.md).

---

## English

Graphical interface for [gnirehtet](https://github.com/Genymobile/gnirehtet): an Android
phone uses the **computer's internet connection over the USB cable** (reverse tethering),
no root required. Works on Windows and Linux.

**Features**
- Downloads gnirehtet (SHA-256 verified) and adb by itself and keeps them on the computer.
- List of connected phones with **real-time speed and traffic** for each one.
- Start, stop and reset the tunnel with one click; several phones at once.
- **Autorun**: enables tethering on every phone you plug in.
- Notification-area icon and **notifications** on connect, disconnect and errors.
- **One-click adb update**.
- **Check processes**: finds and closes leftover gnirehtet processes and duplicate copies of the program.
- Interface in **Italian, English and Russian**.
- Console with the full log and a built-in **user manual** (F1).

**Download**: from the [Releases](../../releases) page get `GnirehtetGUI.exe` (Windows)
or `GnirehtetGUI-x86_64.AppImage` (Linux). No Python needed.

**From source**: `pip install -r requirements.txt`, then `python gnirehtet_gui.py`.

Full manual: [docs/MANUAL.md](docs/MANUAL.md).

---

## Русский

Графический интерфейс для [gnirehtet](https://github.com/Genymobile/gnirehtet): телефон
Android пользуется **интернетом компьютера через USB-кабель** (обратный тетеринг),
без root. Работает в Windows и Linux.

**Возможности**
- Сама скачивает gnirehtet (с проверкой SHA-256) и adb и хранит их на компьютере.
- Список подключённых телефонов со **скоростью и трафиком в реальном времени**.
- Включение, остановка и восстановление туннеля одним щелчком; несколько телефонов сразу.
- **Автозапуск**: тетеринг включается на каждом подключённом телефоне.
- Значок в области уведомлений и **уведомления** о подключении, отключении и ошибках.
- **Обновление adb** одной кнопкой.
- **Проверка процессов**: находит и закрывает оставшиеся процессы gnirehtet и лишние копии программы.
- Интерфейс на **итальянском, английском и русском**.
- Консоль с полным журналом и встроенное **руководство пользователя** (F1).

**Скачать**: на странице [Releases](../../releases) возьмите `GnirehtetGUI.exe` (Windows)
или `GnirehtetGUI-x86_64.AppImage` (Linux). Python не нужен.

**Из исходников**: `pip install -r requirements.txt`, затем `python gnirehtet_gui.py`.

Полное руководство: [docs/MANUAL.ru.md](docs/MANUAL.ru.md).

---

## Build

The executables are built by GitHub Actions ([release.yml](.github/workflows/release.yml))
whenever a version tag is pushed:

```
git tag v1.3.0
git push origin v1.3.0
```

## Credits

© 2026 Dmitrij Musella. Licensed under the [Apache License 2.0](LICENSE).

Based on [gnirehtet](https://github.com/Genymobile/gnirehtet) by Genymobile (Apache 2.0).
adb is part of Google's Android SDK Platform Tools.
