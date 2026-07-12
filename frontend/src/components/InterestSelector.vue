<script setup lang="ts">
const props = withDefaults(defineProps<{
  modelValue: string[]
  options: string[]
  disabled?: boolean
  max?: number
}>(), { disabled: false, max: 8 })

const emit = defineEmits<{ 'update:modelValue': [value: string[]] }>()

function toggle(option: string) {
  if (props.disabled) return
  if (props.modelValue.includes(option)) {
    emit('update:modelValue', props.modelValue.filter((item) => item !== option))
    return
  }
  if (props.modelValue.length < props.max) emit('update:modelValue', [...props.modelValue, option])
}
</script>

<template>
  <div class="interest-options" role="group" aria-label="兴趣标签">
    <button
      v-for="option in options"
      :key="option"
      type="button"
      class="interest-option"
      :class="{ selected: modelValue.includes(option) }"
      :aria-pressed="modelValue.includes(option)"
      :disabled="disabled || (!modelValue.includes(option) && modelValue.length >= max)"
      @click="toggle(option)"
    >
      {{ option }}
    </button>
  </div>
</template>
