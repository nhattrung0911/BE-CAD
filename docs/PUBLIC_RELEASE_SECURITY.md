# Public Release Security Check

This repository is safe to make public when these checks stay true:

- no real `.env` file is committed;
- `.env.example` contains placeholders only;
- no generated DB files, storage artifacts, logs, `node_modules`, or build output are tracked;
- no private keys, access tokens, cloud credentials, or customer data are committed;
- production secrets are provided by the deployment environment or secret manager;
- admin ingestion is protected by `ADMIN_API_KEY` and must not be exposed without auth;
- production deployments must set `AUTO_CREATE_SCHEMA=false` and run Alembic migrations explicitly.

Recommended pre-public scan:

```powershell
rg -n -i "(password|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|client[_-]?secret|bearer|authorization|credential|DATABASE_URL|POSTGRES_|MINIO_|AWS_|S3_)" . -g "!frontend-demo/node_modules" -g "!frontend-demo/dist" -g "!backend/storage" -g "!**/__pycache__/**"
git ls-files | rg -n "(\.env$|storage/|\.db$|\.sqlite|\.log$|node_modules|dist/|__pycache__|\.pem$|\.key$|id_rsa|credentials)"
```

Expected tracked env file:

- `infra/.env.example`

Do not commit any copied `.env` file.
