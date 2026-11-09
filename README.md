# STOCKFLOW V7 — Warehouse Analytics

Independent Flask + SQLite demo app. **This is a new database schema, not a drop-in upgrade for V5/V6.** Do not copy V5/V6 `stock.db` into this project without migration.

## Run on Windows VS Code (PowerShell)

1. File > Open Folder > choose the inner `stock-management-v7` folder containing `app.py`.
2. In Terminal:

```powershell
python -m pip install -r requirements.txt
python app.py --seed-demo
python -m flask --app app run --host 127.0.0.1 --port 5050 --no-reload
```

3. Open http://127.0.0.1:5050 (do not use port 5060, which Chrome blocks).

Demo accounts created only on a **fresh empty DB** using `--seed-demo`:

- admin / `DemoAdmin#2026!`
- staff / `DemoStaff#2026!`

For a new real database, **skip `--seed-demo`** and visit `/setup` to create the first Admin account.

To check the active source path:

```powershell
python -c "import app; print(app.__file__)"
```

## Features

- Login, hashed passwords, Admin/Staff authorization
- Dashboard KPIs, Chart.js 14-day trends and inventory health
- Inventory create/edit, stock thresholds
- IN/OUT with negative stock prevention, movement audit history
- Analytics charts, CSV export with UTF-8 BOM for Excel
- User creation (Admin only)
- Thai time UTC+7, responsive design

## Deployment (Render free demo)

1. Create a **private** GitHub repo, upload this project. Do not upload `stock.db`, `.env`, secrets or real customer data.
2. Render > New > Blueprint > select repository > apply `render.yaml` (confirm the free plan is available).
3. Open Render URL, go to `/setup` and create an admin (no default credentials unless you manually seed local DB).
4. Render free instances use **ephemeral disk**. SQLite data can disappear on restart/deploy; only use disposable demo data. Render may sleep when idle. For production, migrate to managed persistent PostgreSQL, add migrations/backups, monitoring, secure sessions, rate limits, and concurrency testing.

## Security and scope

This is a **demo / prototype**, not a production-ready ERP. The local SQLite file is not suitable for real shared cloud inventory. Sessions reset when secret changes; configure a stable secret. Chart.js and Google Fonts require internet; charts will not display offline. No CSV import, password reset, pagination or multi-warehouse features yet.
