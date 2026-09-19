# Remote Runtime V0.1 — Render

**Status:** Deployment-ready remote runtime.

## Why

Codespaces remains useful for interactive development, but Body hardware testing no longer depends
on a Codespace being available.

The runtime is deployed as a normal HTTPS web service. The user's browser remains the hardware
bridge for camera, microphone, speakers, and display.

```text
Windows browser
  ↕ HTTPS
Render web service
  ↕
Atlas + reasoning API
```

No Python application process runs on the Windows machine.

## Provider

Render is the V0.1 remote host.

The repository-root `render.yaml` defines one Python web service:

- service: `ai-cognitive-mind`;
- region: Ohio;
- plan: Free;
- Python: 3.12;
- health check: `/health`;
- start command: `uvicorn aicognitive_mind.api:app --host 0.0.0.0 --port $PORT`;
- persistent cognitive storage: existing MongoDB Atlas deployment.

Render's local filesystem is not cognitive storage.

## Secrets required during first deployment

The Blueprint asks for three values and does not commit them to Git:

### MONGODB_URI

The canonical Atlas connection string.

The service explicitly sets:

```text
STORAGE_PROVIDER=mongo
MONGODB_DATABASE=ai_cognitive_mind
```

This preserves the current Atlas Mind and does not activate the parked Surreal migration.

### OPENAI_API_KEY

Used by the current reasoning engine and Mind-side visual/audio interpretation.

### APP_ACCESS_PASSWORD

Protects the entire browser application and API.

The username is:

```text
mind
```

Use a unique password. It is a deployment credential, not identity or cognitive memory.

## Public-network boundary

Render web services have a public HTTPS hostname, but this application requires HTTP Basic
authentication whenever `APP_ACCESS_PASSWORD` is configured.

Only `/health` remains unauthenticated so Render can perform service health checks.

This protection covers:

- the Mind portal;
- memory and journal APIs;
- Live Body;
- Eyes / Ears / Face / Mouth pages;
- Body and Mind APIs;
- FastAPI-generated endpoints.

## Deployment

After this file and `render.yaml` are merged into `main`, create the Render Blueprint from the
GitHub repository and provide the three secret values above.

Render will build directly from GitHub. Future pushes to the Blueprint-managed branch can deploy
new application versions without requiring Codespaces.

## Hardware test

After Render reports the service as live:

1. open its HTTPS `onrender.com` URL;
2. authenticate as `mind`;
3. open `/body/live`;
4. allow camera and microphone permissions;
5. test **See through camera** and **Listen for 5 seconds**.

Because the page is delivered over HTTPS, browser camera and microphone APIs can operate without
a local application server.

## Free-plan behavior

The free service is intended for prototype/hobby testing. It may spin down when idle and take
additional time to answer the first request after inactivity.

If the Mind later needs to stay continuously awake, move the same service to paid compute rather
than changing the architecture.
