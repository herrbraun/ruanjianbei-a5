import { defineStore } from 'pinia'

import type { ScenicArea } from '@/api/knowledge'

const storageKey = 'selected_scenic_area'

function readStoredArea(): ScenicArea | null {
  try {
    const raw = localStorage.getItem(storageKey)
    return raw ? JSON.parse(raw) as ScenicArea : null
  } catch {
    localStorage.removeItem(storageKey)
    return null
  }
}

export const useScenicStore = defineStore('scenic', {
  state: () => ({ selectedArea: readStoredArea() as ScenicArea | null }),
  getters: {
    selectedCode: (state) => state.selectedArea?.code || '',
    selectedName: (state) => state.selectedArea?.name || '',
  },
  actions: {
    select(area: ScenicArea) {
      this.selectedArea = area
      localStorage.setItem(storageKey, JSON.stringify(area))
    },
    clear() {
      this.selectedArea = null
      localStorage.removeItem(storageKey)
    },
  },
})
