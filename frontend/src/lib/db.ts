import Database from "better-sqlite3"
import { drizzle } from "drizzle-orm/better-sqlite3"
import * as schema from "./schema"
import path from "path"

const DB_PATH = process.env.DATABASE_PATH || path.join(process.cwd(), "data", "knowledge.db")

// Ensure data directory exists
import fs from "fs"
const dir = path.dirname(DB_PATH)
if (!fs.existsSync(dir)) {
  fs.mkdirSync(dir, { recursive: true })
}

const sqlite = new Database(DB_PATH)
sqlite.pragma("journal_mode = WAL")
sqlite.pragma("foreign_keys = ON")

export const db = drizzle(sqlite, { schema })
export { sqlite }
