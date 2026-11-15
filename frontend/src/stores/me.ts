// /me: ομάδα, avatar, photo_status. Φορτώνεται μετά την είσοδο· ξαναφορτώνεται πριν από τη φωτογραφία (S05).
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { getMe, updateMe, type Me } from '@/api/me'

export const useMeStore = defineStore('me', () => {
  const me = ref<Me | null>(null)
  const loading = ref(false)

  const photoStatus = computed(() => me.value?.photo_status ?? 'unavailable')
  const avatarId = computed(() => me.value?.avatar_id ?? null)

  async function load(force = false): Promise<Me | null> {
    if (me.value && !force) return me.value
    loading.value = true
    try {
      me.value = await getMe()
    } finally {
      loading.value = false
    }
    return me.value
  }

  async function setAvatar(avatarId: string): Promise<void> {
    me.value = await updateMe(avatarId)
  }

  function clear(): void {
    me.value = null
  }

  return { me, loading, photoStatus, avatarId, load, setAvatar, clear }
})
