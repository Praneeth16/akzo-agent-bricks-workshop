/**
 * Minimal ambient types for `pg`. We deliberately do NOT depend on `@types/pg`
 * because that package pulls a runtime `pg-types@^4` tree (pg-numeric, ...) whose
 * newest tarballs are not mirrored by the Databricks Apps npm proxy, breaking the
 * deploy. This shim covers only the surface server/lakebase.ts uses.
 */
declare module 'pg' {
  export interface PoolConfig {
    host?: string;
    port?: number;
    database?: string;
    user?: string;
    password?: string | (() => string | Promise<string>);
    ssl?: boolean | { rejectUnauthorized?: boolean };
    max?: number;
    idleTimeoutMillis?: number;
    connectionTimeoutMillis?: number;
  }
  export interface QueryResult<R = Record<string, unknown>> {
    rows: R[];
    rowCount: number;
  }
  export interface PoolClient {
    query(text: string): Promise<unknown>;
  }
  export class Pool {
    constructor(config?: PoolConfig);
    query<R = Record<string, unknown>>(text: string, params?: unknown[]): Promise<QueryResult<R>>;
    on(event: 'connect', listener: (client: PoolClient) => void): this;
    end(): Promise<void>;
  }
  // pg is CommonJS: the value is reached via the default import (`import pg from 'pg'`),
  // while `Pool` is used as a type-only import.
  const pg: { Pool: typeof Pool };
  export default pg;
}
