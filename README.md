# wishly

Wunschlisten für Familien und Freundeskreise: Listen für Geburtstag, Weihnachten, Hochzeit oder
Babyparty anlegen, mit der Familie oder per Link teilen und Geschenke reservieren – ohne dass die
beschenkte Person sieht, was schon besorgt wurde.

## Funktionen

- **Konten und Familien** – Registrierung, Anmeldung, Passwort zurücksetzen. Familien werden über
  einen Einladungslink geteilt; Administratoren verwalten Mitglieder und Rollen.
- **Kinderprofile** – Kinder brauchen kein Konto; ihre Erziehungsberechtigten pflegen die Listen
  und sehen (anders als bei eigenen Listen) auch die Reservierungen.
- **Kinder-Link** – über einen geheimen Link (z. B. als Lesezeichen auf dem Tablet) tragen Kinder
  ohne Konto selbst Wünsche ein und können ihre eigenen ändern oder wegnehmen. Reservierungen und
  geheime Vorschläge sehen sie dort nicht. Pro Kind einstellbar: neue Wünsche erscheinen sofort
  oder erst nach Freigabe durch die Erziehungsberechtigten. Der Link lässt sich erneuern und
  abschalten.
- **Geburtstage** – Tag und Monat im Profil; die Übersicht zeigt die nächsten 60 Tage, und die
  Familie bekommt rechtzeitig eine E-Mail (Standard: 14 Tage vorher).
- **Wunschlisten** – nach Anlass, mit Datum und Beschreibung; das Design folgt dem Anlass oder der
  Jahreszeit oder wird fest gewählt.
- **Wünsche** – Titel, Beschreibung, Bild, Shop-Link, Preis, Priorität (1–5 Sterne), gewünschte
  Anzahl und Notizen (Größe, Farbe …).
- **Reservieren** – „Reserviert“ oder „Gekauft / erhalten“, auch nur ein Teil der Anzahl. Unter
  *Besorgungen* stehen alle eigenen Reservierungen.
- **Überraschungsschutz** – die beschenkte Person sieht weder Reservierungen noch geheime
  Vorschläge, auch nicht über den öffentlichen Link.
- **Vorschläge** – Familienmitglieder schlagen Wünsche vor: *zur Bestätigung* (erscheint erst nach
  Annahme) oder *geheim* (für alle außer der beschenkten Person sichtbar).
- **Öffentlicher Link** – pro Liste zuschaltbar, gut zu merken: `/<familie>/<name>/` zeigt alle
  öffentlichen Listen einer Person (bei nur einer direkt diese), `/<familie>/<name>/<liste>/` eine
  bestimmte, z. B. `/mueller/anna/weihnachten-2026/`. Die Namen entstehen automatisch (Umlaute
  als ae/oe/ue/ss) und lassen sich bei Familie, Profil und Liste ändern. Gäste reservieren ohne
  Konto mit ihrem Namen. Weil solche Links erratbar sind, gilt eine öffentliche Liste als
  öffentlich – zurückgezogen wird sie, indem man den öffentlichen Link abschaltet.
- **Link einfügen genügt** – oben auf der eigenen Liste reicht ein Shop-Link: Name, Bild, Preis
  und Beschreibung kommen aus der Shopseite (strukturierte Daten, OpenGraph, Amazon), was nicht
  gefunden wird, bleibt leer. Im ausführlichen Formular (auch beim Kinder-Link) werden die Felder
  schon beim Einfügen des Links gefüllt, sodass man vor dem Speichern sieht, was gefunden wurde.
  Selbst eingetragene Felder bleiben unangetastet; „Neu einlesen“ holt alles neu aus dem Link.
- **Affiliate** – Amazon-Links bekommen beim Anzeigen den eigenen Partner-Tag
  (`WISHLY_AMAZON_TAG`); gespeichert wird der Link unverändert.
- **Preisvergleich** – ein Link zur Preissuche bei idealo.

## Entwicklung

Voraussetzung: [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Die Seite läuft dann unter http://127.0.0.1:8000, die Django-Verwaltung unter `/verwaltung/`.
Ohne `CELERY_BROKER_URL` laufen Hintergrundaufgaben direkt im Webprozess, ohne `EMAIL_HOST`
erscheinen E-Mails in der Konsole – für die Entwicklung braucht es weder Redis noch Mailserver.

```sh
uv run python manage.py test                              # alle Tests
uv run python manage.py makemigrations --check --dry-run  # Migrationen vollständig?
```

## Betrieb mit Docker

```sh
cp .env.example .env   # mindestens DJANGO_SECRET_KEY und POSTGRES_PASSWORD setzen
docker compose up -d --build
```

Danach läuft wishly unter http://localhost:8000 (Port über `APP_PORT`). Der Stack besteht aus
`web` (gunicorn), `worker` (liest Shopseiten ein), `beat` (Geburtstags-Erinnerungen), `db`
(PostgreSQL 17) und `redis`. Migrationen laufen beim Start von `web` automatisch; mit
`DJANGO_SUPERUSER_USERNAME`/`_PASSWORD` wird beim ersten Start ein Admin-Konto angelegt.
TLS übernimmt ein Reverse-Proxy davor (`DJANGO_BEHIND_HTTPS_PROXY=true`).

Ohne Docker und alle Einstellungen im Detail: [docs/betrieb.md](docs/betrieb.md).

## Grenzen

- Namen von Profilen sind über alle Familien hinweg eindeutig (Erwachsene können in mehreren
  Familien sein) – die zweite Anna heißt in Links `anna-2`, bis man es ändert. Gehört eine Person
  mehreren Familien an, steht in ihren Links die Familie, der sie zuerst beigetreten ist; die
  Links funktionieren aber mit jeder ihrer Familien.

- Manche Shops (z. B. Thalia, LEGO, Galaxus) sperren automatische Abrufe mit einem Bot-Schutz.
  Dann bleibt der Wunsch mit dem Link bestehen und Titel, Bild und Preis werden von Hand
  eingetragen. Ein Browser-Abruf (Playwright) ist bewusst noch nicht eingebaut – er bräuchte
  einen Browser auf dem Server.
- Der Preisvergleich ist ein Suchlink, kein automatischer Abgleich.
- Produktbilder werden direkt vom Shop geladen, nicht auf dem Server gespeichert.
