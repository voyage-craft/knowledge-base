import { sqliteTable, text, integer, real } from "drizzle-orm/sqlite-core"
import { sql } from "drizzle-orm"

// Users
export const users = sqliteTable("users", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  username: text("username").notNull().unique(),
  email: text("email").notNull().unique(),
  hashedPassword: text("hashed_password").notNull(),
  isActive: integer("is_active", { mode: "boolean" }).default(true),
  isAdmin: integer("is_admin", { mode: "boolean" }).default(false),
  createdAt: text("created_at").default(sql`(datetime('now'))`),
  updatedAt: text("updated_at").default(sql`(datetime('now'))`),
})

// Documents
export const documents = sqliteTable("documents", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  title: text("title").notNull(),
  contentJson: text("content_json"), // TipTap JSON stored as text
  latexSource: text("latex_source"),
  status: text("status").default("draft"), // draft, published, archived, deleted
  folderId: integer("folder_id").references(() => folders.id),
  userId: integer("user_id").notNull().references(() => users.id),
  version: integer("version").default(1),
  createdAt: text("created_at").default(sql`(datetime('now'))`),
  updatedAt: text("updated_at").default(sql`(datetime('now'))`),
})

// Document versions (history)
export const documentVersions = sqliteTable("document_versions", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  documentId: integer("document_id").notNull().references(() => documents.id),
  contentJson: text("content_json"),
  latexSource: text("latex_source"),
  versionNumber: integer("version_number").notNull(),
  createdAt: text("created_at").default(sql`(datetime('now'))`),
})

// Folders
export const folders = sqliteTable("folders", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  name: text("name").notNull(),
  parentId: integer("parent_id"),
  position: integer("position").default(0),
  userId: integer("user_id").notNull().references(() => users.id),
  createdAt: text("created_at").default(sql`(datetime('now'))`),
})

// Tags
export const tags = sqliteTable("tags", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  name: text("name").notNull().unique(),
  color: text("color").default("#3B82F6"),
  userId: integer("user_id").notNull().references(() => users.id),
})

// Document-Tag association
export const documentTags = sqliteTable("document_tags", {
  documentId: integer("document_id").notNull().references(() => documents.id),
  tagId: integer("tag_id").notNull().references(() => tags.id),
})

// Export jobs
export const exportJobs = sqliteTable("export_jobs", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  documentId: integer("document_id").notNull().references(() => documents.id),
  format: text("format").notNull(), // pdf, docx, html, epub, markdown
  templateName: text("template_name").default("default"),
  status: text("status").default("pending"), // pending, processing, completed, failed
  outputPath: text("output_path"),
  errorMessage: text("error_message"),
  userId: integer("user_id").notNull().references(() => users.id),
  createdAt: text("created_at").default(sql`(datetime('now'))`),
  completedAt: text("completed_at"),
})

// Embeddings (for RAG, using regular table - sqlite-vec would be a separate extension)
export const embeddings = sqliteTable("embeddings", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  documentId: integer("document_id").notNull().references(() => documents.id),
  chunkIndex: integer("chunk_index").notNull(),
  chunkText: text("chunk_text").notNull(),
  embeddingJson: text("embedding_json"), // Store as JSON array string
  metadata: text("metadata"), // JSON string
  createdAt: text("created_at").default(sql`(datetime('now'))`),
})
