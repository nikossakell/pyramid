// POST /auth/login — κλειδί πρόσβασης → JWT. Ίδιο 401 για κάθε αποτυχία· 429 με Retry-After· 403 not_yet_available / study_ended.
import { api } from './client'

export type TokenResponse = { access_token: string; token_type: string; expires_in: number }

export function login(accessKey: string): Promise<TokenResponse> {
  return api.post<TokenResponse>('/auth/login', { access_key: accessKey }, { auth: false })
}
