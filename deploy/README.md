# Deploy Quickstart

## 1) Prepare config files

Copy examples:

- `cp deploy/.env.example deploy/.env`
- `cp deploy/odoo.conf.example deploy/odoo.conf`

Then edit:

- `deploy/.env` for DB credentials.
- `deploy/odoo.conf` for the same credentials.

## 2) Start Odoo + Postgres

```bash
docker compose -f deploy/docker-compose.yml up -d
```

## 3) Run module upgrade after pull

Linux/macOS:

```bash
sh scripts/post_deploy.sh
```

Windows PowerShell:

```powershell
.\scripts\post_deploy.ps1
```

## 4) Verify

- Open `http://<server-ip>:8069`
- Check logs:

```bash
docker compose -f deploy/docker-compose.yml logs -f odoo
```
