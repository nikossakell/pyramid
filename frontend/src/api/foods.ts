// /food-groups και /foods/search — μόνο κωδικοί και ονόματα. Το `sort` είναι σειρά εμφάνισης, όχι τιμή θρεπτικού.
import { api } from './client'

export type FoodGroup = { code: string; label_el: string; shown: boolean; sort: number }
export type Food = { food_id: string; name_el: string; food_group: string }

export const getFoodGroups = () => api.get<FoodGroup[]>('/food-groups')
export const searchFoods = (q: string, group?: string) => api.get<Food[]>('/foods/search', { q, group })
