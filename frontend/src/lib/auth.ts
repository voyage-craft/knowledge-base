import { jwtVerify, SignJWT } from "jose"

const secretKey = process.env.JWT_SECRET_KEY

if (!secretKey) {
  console.error(
    "[AUTH] JWT_SECRET_KEY is not set! " +
    "Set JWT_SECRET_KEY in .env.local to match the backend's key. " +
    "Token verification will fail until this is configured."
  )
}

// When JWT_SECRET_KEY is missing, use a placeholder that will cause
// verifyToken() to return null (token verification will fail gracefully)
const JWT_SECRET = new TextEncoder().encode(secretKey || "NOT-SET-DO-NOT-USE")

export interface JWTPayload {
  sub: string
  username: string
  type: "access" | "refresh"
}

export async function verifyToken(token: string): Promise<JWTPayload | null> {
  try {
    const { payload } = await jwtVerify(token, JWT_SECRET)
    return payload as unknown as JWTPayload
  } catch {
    return null
  }
}

export async function createToken(payload: JWTPayload, expiresIn: string = "15m"): Promise<string> {
  return new SignJWT(payload as any)
    .setProtectedHeader({ alg: "HS256" })
    .setExpirationTime(expiresIn)
    .setIssuedAt()
    .sign(JWT_SECRET)
}
