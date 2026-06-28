import express from 'express';
import { createApp, server, analytics } from '@databricks/appkit';
import { registerHackRoutes } from './routes.js';
import { ensureSchema } from './schema.js';

// autoStart: false so we can mount custom hackathon routes on the Express app
// before it starts listening (the server plugin's deferred phase still wires
// plugin routes under /api/<plugin>). analytics() powers the live "Try it live"
// charts over the akzo_* Unity Catalog tables via the SQL warehouse.
const appkit = await createApp({
  plugins: [server({ autoStart: false }), analytics({})],
});

appkit.server.extend((app) => {
  app.use(express.json());
  registerHackRoutes(app);
});

// Ensure the hack_* tables exist + are seeded. Idempotent; tolerate a cold
// Lakebase locally so the UI still boots for frontend work.
try {
  await ensureSchema();
  console.log('[hack] Lakebase schema ready');
} catch (err) {
  console.error('[hack] schema init failed (continuing without seed):', err);
}

await appkit.server.start();
