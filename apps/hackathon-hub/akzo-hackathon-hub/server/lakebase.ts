/**
 * Lakebase (managed Postgres) access for the Hackathon hub — the Node port of
 * apps/_shared/lakebase.py. AppKit's `lakebase` plugin targets the newer Postgres
 * *projects* API; our shared instance `graphrag-spike` is a classic Database
 * Instance, so we connect directly with `pg` + a short-lived OAuth credential.
 *
 * Identity: whoever the Databricks SDK config authenticates as — the developer's
 * email locally, the app service principal when deployed. The credential is the
 * pg password; it expires ~1h, so we cache + refresh transparently. search_path
 * is pinned to the `akzo` schema where every workshop write-back table lives.
 */
import pg from 'pg';
import type { Pool } from 'pg';
import { randomUUID } from 'node:crypto';
import { Config } from '@databricks/sdk-experimental';

const INSTANCE = process.env.LAKEBASE_INSTANCE ?? 'graphrag-spike';
const HOST =
  process.env.PGHOST ?? 'ep-spring-block-d2tu1slg.database.us-east-1.cloud.databricks.com';
const DB_NAME = process.env.PGDATABASE ?? 'databricks_postgres';
const SCHEMA = process.env.LAKEBASE_SCHEMA ?? 'akzo';
// Refresh a little before the ~1h expiry to avoid mid-request failures.
const TOKEN_TTL_MS = 45 * 60 * 1000;

let _cfg: Config | null = null;
async function config(): Promise<Config> {
  if (!_cfg) {
    const cfg = new Config({ profile: process.env.DATABRICKS_CONFIG_PROFILE });
    await cfg.ensureResolved();
    _cfg = cfg;
  }
  return _cfg;
}

async function authHeader(): Promise<string> {
  const h = new Headers();
  await (await config()).authenticate(h);
  const auth = h.get('Authorization');
  if (!auth) throw new Error('Databricks authentication produced no Authorization header');
  return auth;
}

let _user: string | null = null;
/** The identity the SDK authenticates as (email locally, SP when deployed). */
export async function currentUser(): Promise<string> {
  if (_user) return _user;
  const cfg = await config();
  const res = await fetch(`${cfg.host}/api/2.0/preview/scim/v2/Me`, {
    headers: { Authorization: await authHeader() },
  });
  if (!res.ok) throw new Error(`SCIM Me failed: ${res.status} ${await res.text()}`);
  const me = (await res.json()) as { userName?: string };
  if (!me.userName) throw new Error('SCIM Me returned no userName');
  _user = me.userName;
  return _user;
}

let _token: string | null = null;
let _tokenExp = 0;
async function dbToken(): Promise<string> {
  if (_token && Date.now() < _tokenExp) return _token;
  const cfg = await config();
  const res = await fetch(`${cfg.host}/api/2.0/database/credentials`, {
    method: 'POST',
    headers: { Authorization: await authHeader(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ instance_names: [INSTANCE], request_id: randomUUID() }),
  });
  if (!res.ok) throw new Error(`generate-database-credential failed: ${res.status} ${await res.text()}`);
  const cred = (await res.json()) as { token: string };
  _token = cred.token;
  _tokenExp = Date.now() + TOKEN_TTL_MS;
  return _token;
}

// node-postgres pool. The async password provider is invoked per new connection,
// so an expired cached credential is refreshed before the next connect; search_path
// is set on each new connection so every query lands in the akzo schema.
let _pool: Pool | null = null;
export async function getPool(): Promise<Pool> {
  if (_pool) return _pool;
  const user = await currentUser();
  const pool = new pg.Pool({
    host: HOST,
    port: 5432,
    database: DB_NAME,
    user,
    password: dbToken,
    ssl: { rejectUnauthorized: false },
    max: 5,
    idleTimeoutMillis: 30_000,
    connectionTimeoutMillis: 10_000,
  });
  pool.on('connect', (client) => {
    void client.query(`SET search_path TO ${SCHEMA}`);
  });
  _pool = pool;
  return _pool;
}

/** Run a query and return the rows. Params use $1, $2, ... placeholders. */
export async function query<T = Record<string, unknown>>(
  text: string,
  params: unknown[] = []
): Promise<T[]> {
  const pool = await getPool();
  const res = await pool.query(text, params);
  return res.rows as T[];
}

/** Run a write and return the first RETURNING row (or null). */
export async function execute<T = Record<string, unknown>>(
  text: string,
  params: unknown[] = []
): Promise<T | null> {
  const rows = await query<T>(text, params);
  return rows[0] ?? null;
}

export const lakebaseSchema = SCHEMA;
