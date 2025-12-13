# Bug Fix: Bot Start Problem

**Problem:** Wenn auf "Bot starten" geklickt wird, wird die Seite nicht mehr erreichbar (API-Server blockiert).

**Ursache:** 
1. Der Bot-Control-Endpunkt setzt nur den Status im `BotStateManager`
2. `main.py` läuft nicht im Container - der Container startet nur den API-Server
3. Es gibt keinen separaten Bot-Prozess, der auf Status-Änderungen reagiert

**Lösung:**
Der Bot sollte als separater Prozess/Thread laufen ODER als separater Docker Service.
Aktuell wird nur der Status gesetzt, aber es passiert nichts weiter.

**Sofort-Fix:**
Der API-Server sollte nie blockieren. Wenn beim Start ein Fehler auftritt, sollte dieser abgefangen werden.

