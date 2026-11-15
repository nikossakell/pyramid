// GET /feedback/today — μόνο κείμενα (εγκεκριμένα πρότυπα) και κωδικοί ομάδων. Χωρίς rule_id ή αριθμούς.
import { api } from './client'

export type FeedbackMessage = { id: string; text: string }
export type Feedback = { messages: FeedbackMessage[]; food_groups_today: string[] }

export const getFeedbackToday = () => api.get<Feedback>('/feedback/today')
