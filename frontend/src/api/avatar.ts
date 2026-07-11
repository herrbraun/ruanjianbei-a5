import { http } from './http'

export type AvatarGender = 'female' | 'male' | 'unspecified'

export interface VoiceOption {
  value: string
  label: string
}

export interface AvatarVariant {
  id: number
  digital_human_id: number
  outfit_name: string
  version: string
  original_filename: string
  file_size: number
  thumbnail_url: string | null
  validation_status: 'ready' | 'failed'
  created_at: string
}

export interface DigitalHuman {
  id: number
  name: string
  gender: AvatarGender
  role_title: string
  introduction: string | null
  tts_voice: string
  tts_instructions: string | null
  is_enabled: boolean
  variants: AvatarVariant[]
}

export interface ScenicAvatar {
  config_id: number
  scenic_area_id: number
  id: number
  digital_human_id: number
  name: string
  gender: AvatarGender
  role_title: string
  introduction: string | null
  outfit_name: string
  version: string
  thumbnail_url: string | null
  file_size: number
  is_enabled: boolean
  is_default: boolean
  sort_order: number
}

export interface ScenicAvatarList {
  scenic_area_id: number
  default_variant_id: number | null
  avatars: ScenicAvatar[]
}

export interface DigitalHumanPayload {
  name: string
  gender: AvatarGender
  role_title: string
  introduction?: string | null
  tts_voice: string
  tts_instructions?: string | null
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api'

export function avatarAssetUrl(scenicAreaCode: string, avatarVariantId: number) {
  return `${apiBaseUrl}/avatars/scenic-areas/${encodeURIComponent(scenicAreaCode)}/variants/${avatarVariantId}/asset`
}

export const avatarApi = {
  listVoices: () => http.get<VoiceOption[]>('/admin/avatars/voices'),
  listHumans: () => http.get<DigitalHuman[]>('/admin/avatars/humans'),
  createHuman: (data: DigitalHumanPayload) => http.post<DigitalHuman>('/admin/avatars/humans', data),
  updateHuman: (id: number, data: Partial<DigitalHumanPayload> & { is_enabled?: boolean }) =>
    http.patch<DigitalHuman>(`/admin/avatars/humans/${id}`, data),
  deleteHuman: (id: number) => http.delete<void>(`/admin/avatars/humans/${id}`),
  listScenicConfigs: (scenicAreaId: number) => http.get<ScenicAvatar[]>('/admin/avatars/scenic-configs', { params: { scenic_area_id: scenicAreaId } }),
  uploadVariant: (data: {
    digitalHumanId: number
    scenicAreaId: number
    outfitName: string
    version: string
    thumbnailUrl?: string
    isEnabled: boolean
    isDefault: boolean
    sortOrder: number
    file: File
  }) => {
    const form = new FormData()
    form.append('digital_human_id', String(data.digitalHumanId))
    form.append('scenic_area_id', String(data.scenicAreaId))
    form.append('outfit_name', data.outfitName)
    form.append('version', data.version)
    if (data.thumbnailUrl) form.append('thumbnail_url', data.thumbnailUrl)
    form.append('is_enabled', String(data.isEnabled))
    form.append('is_default', String(data.isDefault))
    form.append('sort_order', String(data.sortOrder))
    form.append('file', data.file)
    return http.post<ScenicAvatar>('/admin/avatars/variants', form)
  },
  updateVariant: (id: number, data: { outfit_name?: string; version?: string; thumbnail_url?: string | null }) =>
    http.patch<AvatarVariant>(`/admin/avatars/variants/${id}`, data),
  deleteVariant: (id: number) => http.delete<void>(`/admin/avatars/variants/${id}`),
  updateScenicConfig: (id: number, data: { is_enabled?: boolean; is_default?: boolean; sort_order?: number }) =>
    http.patch<ScenicAvatar>(`/admin/avatars/scenic-configs/${id}`, data),
  listPublicScenicAvatars: (scenicAreaCode: string) => http.get<ScenicAvatarList>(`/avatars/scenic-areas/${scenicAreaCode}`),
}
