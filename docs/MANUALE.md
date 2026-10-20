# Manuale utente — Pupovina 1.4.0

*di Dmitrij Musella*

## A cosa serve

Pupovina permette a un telefono Android di **usare la connessione internet del
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
   versione ufficiale Rust 2.5.1, ne verifica l'impronta SHA-256 e la installa.
2. Se adb non è già presente sul computer, premi **Scarica adb (platform-tools)**.
   Viene scaricato dal sito ufficiale Android.
3. Collega il telefono. Sullo schermo compare la richiesta *Consentire il debug USB?*:
   accettala (meglio con *Consenti sempre da questo computer*).
4. Seleziona il telefono nell'elenco e premi **Avvia tethering**.
5. La prima volta l'app gnirehtet viene installata sul telefono, che chiede di
   **consentire una connessione VPN**: conferma. Quando è attiva, nella barra di stato
   del telefono compare l'icona a forma di chiave.

Gli strumenti scaricati restano sul computer, nella cartella:

`Windows: %LOCALAPPDATA%\GnirehtetGUI\tools — Linux: ~/.local/share/GnirehtetGUI/tools`

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

Pupovina — © 2026 Dmitrij Musella.

Basato su [gnirehtet](https://github.com/Genymobile/gnirehtet) di Genymobile,
distribuito con licenza Apache 2.0. adb fa parte degli Android SDK Platform Tools di Google.
