/** C06 AvatarPicker: τα 8 avatars των mockups → τα 8 πρώτα id της κλειστής λίστας AVATAR_IDS του backend (avatar_01…).
 *  Τα avatar_09–12 του backend δεν έχουν σχέδιο ακόμα και δεν προσφέρονται. */
export type Avatar = { id: string; label: string; bg: string; fg: string; path: string }

export const AVATARS: Avatar[] = [
  { id: 'avatar_01', label: 'Μπάλα', bg: '#B1318E', fg: '#FFFFFF', path: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z M12 3c-3 3-3 15 0 18 M12 3c3 3 3 15 0 18 M3 12h18' },
  { id: 'avatar_02', label: 'Μήλο', bg: '#F14711', fg: '#000000', path: 'M12 7c-4-2-8 1-8 6 0 4 3 8 5 8 1 0 2-1 3-1s2 1 3 1c2 0 5-4 5-8 0-5-4-8-8-6z M12 7V4 M12 4c1-1 2-1 3-1' },
  { id: 'avatar_03', label: 'Κεραυνός', bg: '#000000', fg: '#F14711', path: 'M13 2L5 14h6l-1 8 9-13h-6z' },
  { id: 'avatar_04', label: 'Φύλλο', bg: '#418A4A', fg: '#000000', path: 'M5 19c0-8 5-13 14-14 0 9-5 14-14 14z M5 19l7-7' },
  { id: 'avatar_05', label: 'Αστέρι', bg: '#000000', fg: '#FFFFFF', path: 'M12 3l2.7 6 6.3.6-4.8 4.3 1.5 6.1L12 16.8 6.3 20l1.5-6.1L3 9.6l6.3-.6z' },
  { id: 'avatar_06', label: 'Κύμα', bg: '#B1318E', fg: '#FFFFFF', path: 'M3 12c3-4 6-4 9 0s6 4 9 0 M3 18c3-4 6-4 9 0s6 4 9 0' },
  { id: 'avatar_07', label: 'Βουνό', bg: '#F14711', fg: '#000000', path: 'M3 20l6-11 4 6 3-4 5 9z M9 9l2 3' },
  { id: 'avatar_08', label: 'Καρότο', bg: '#418A4A', fg: '#000000', path: 'M14 10L5 21l11-9z M14 10l3-6 M14 10l6-3 M13 11l-3 3' },
]
