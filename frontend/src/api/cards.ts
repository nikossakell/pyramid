// GET /cards — μόνο id, σπανιότητα, ημέρα, αν άνοιξε. Το άνοιγμα (M03) είναι εκτός φάσης.
import { api } from './client'

export type Card = { id: string; tier: 'common' | 'rare' | 'epic'; day: string; opened: boolean }

export const listCards = () => api.get<Card[]>('/cards')
