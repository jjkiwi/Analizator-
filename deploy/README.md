# Uruchamianie w tle

Trzy warianty, wybierz jeden (decyzja 2 w `DECYZJE.md`). We wszystkich:
automatyczny restart po awarii, rotacja logow, a `reports/panel.html` odswieza sam `cfd run`
co `dashboard.refresh_minutes` minut (`config/settings.yaml`, domyslnie 5).

| Srodowisko | Pliki | Restart | Logi |
|---|---|---|---|
| VPS / Raspberry Pi (Linux) | `analizator-cfd.service` | `Restart=always`, co 30 s | journald |
| Dowolny host z Dockerem | `Dockerfile`, `docker-compose.yml` | `restart: unless-stopped` | json-file 5 x 10 MB |
| Wlasny komputer z Windows | `windows-task.ps1` | Harmonogram zadan, co 1 min | `logs\cfd-RRRRMMDD.log`, 14 dni |

Instrukcja jest w naglowku kazdego pliku. Sekrety zawsze tylko w `.env`.

Stan weryfikacji: pliki nie byly uruchomione na docelowym systemie (w srodowisku, w ktorym powstaly,
nie ma systemd, Dockera ani Windows). Sprawdz pierwszy start i logi.
