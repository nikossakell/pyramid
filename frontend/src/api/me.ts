// GET / PATCH /me — μόνο {arm, avatar_id, photo_available, photo_status}.
import { api } from './client'

export type PhotoStatus = 'available' | 'suspended' | 'unavailable'
export type Me = { arm: string; avatar_id: string | null; photo_available: boolean; photo_status: PhotoStatus }

export const getMe = () => api.get<Me>('/me')
export const updateMe = (avatar_id: string) => api.patch<Me>('/me', { avatar_id })
