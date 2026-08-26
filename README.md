# logistics-chatbot

## Deployment

Live (decision-log **D32**):

- **Frontend**: https://main.d3pn3cxdlrbarv.amplifyapp.com (AWS Amplify, manual CLI deploy)
- **API**: https://logistics-svc.5zz1a2nkpxpzc.ap-southeast-1.cs.amazonlightsail.com (Lightsail container service: backend + Postgres; the DB is ephemeral and reseeded from `infra/data/` on every boot)

The frontend is built with `VITE_API_BASE_URL` pointing at the API; the backend allows that
one origin via `CORS_ALLOW_ORIGINS`. Locally neither is set — nginx keeps everything on one
origin exactly as before.

Deploy tooling lives in `infra/deploy/` which is **gitignored on purpose** (local-only):
`deploy-lightsail.ps1` builds and ships the backend + DB images, `deploy-frontend.ps1`
builds and ships the frontend. A clone of this repo therefore cannot redeploy; the live
URLs above and decision-log D32 are the record of how it runs.
