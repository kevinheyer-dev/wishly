# Changelog

## Unveröffentlicht

### Neu

- Konten mit Registrierung, Anmeldung, Passwort ändern und zurücksetzen.
- Familien mit Einladungslink, Rollen (Administrator, Familienmitglied) und Kinderprofilen ohne
  eigenes Konto, die von Erziehungsberechtigten gepflegt werden.
- Geburtstag (Tag und Monat) im Profil, Übersicht der nächsten Geburtstage und E-Mail-Erinnerung
  vor dem Geburtstag.
- Wunschlisten nach Anlass (Geburtstag, Hochzeit, Weihnachten, Babyparty, Sonstiges) mit
  passendem oder jahreszeitlichem Design.
- Wünsche mit Titel, Beschreibung, Bild, Link, Preis, Priorität (1–5 Sterne), Anzahl und Notizen.
- Reservieren und als gekauft markieren, inklusive Anzahl; Überraschungsschutz für Beschenkte.
- Vorschläge von Familienmitgliedern: zur Bestätigung oder geheim.
- Kinder-Link: Kinder tragen ohne Konto selbst Wünsche ein; Freigabe durch die
  Erziehungsberechtigten pro Kind einstellbar.
- Öffentlicher Link pro Liste mit gut merkbarer Adresse `/<familie>/<name>/<liste>/`; Gäste
  reservieren ohne Konto.
- Produktdaten werden aus dem Shop-Link gelesen (im Hintergrund über Celery).
- Wunsch nur per Link anlegen; im Formular werden Name, Bild, Preis und Beschreibung schon beim
  Einfügen des Links ausgefüllt. „Neu einlesen“ übernimmt alle Angaben neu aus dem Link.
- Amazon-Links bekommen auf Wunsch den eigenen Partner-Tag; Link zum Preisvergleich.
