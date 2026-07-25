<template>
  <section>
    <h1>{{ t('manager.deliveryTitle') }}</h1>
    <div class="a-card" style="max-width:460px">
      <div class="a-field" style="margin-bottom:.8rem">
        <label>{{ t('manager.feeHigh') }}</label>
        <input class="a-input" type="number" min="0" step="0.5" v-model.number="form.fee_high">
      </div>
      <div class="a-field" style="margin-bottom:.8rem">
        <label>{{ t('manager.feeLow') }}</label>
        <input class="a-input" type="number" min="0" step="0.5" v-model.number="form.fee_low">
      </div>
      <div class="a-field" style="margin-bottom:.4rem">
        <label>{{ t('manager.freeThreshold') }} <span class='dh' role='img' aria-label='درهم'></span></label>
        <input class="a-input" type="number" min="0" step="1" v-model.number="form.free_threshold">
      </div>
      <p class="a-muted" style="font-size:.8rem;margin-bottom:.8rem">{{ t('manager.freeThresholdHint') }}</p>
      <button class="a-btn" :disabled="busy" @click="save">{{ busy ? '…' : t('manager.save') }}</button>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSettingsStore } from '../../stores/settings'
import { useToastStore } from '../../stores/toast'

const { t } = useI18n()
const settings = useSettingsStore()
const toast = useToastStore()
const busy = ref(false)
const form = reactive({ fee_high: 30, fee_low: 25, free_threshold: 250 })

watch(() => settings.delivery, (d) => Object.assign(form, d), { immediate: true, deep: true })

async function save() {
  busy.value = true
  try {
    await settings.updateDelivery({
      fee_high: Number(form.fee_high) || 0,
      fee_low: Number(form.fee_low) || 0,
      free_threshold: Number(form.free_threshold) || 0,
    })
    toast.show(t('manager.deliverySaved'))
  } catch (e) {
    toast.show(e.message)
  } finally {
    busy.value = false
  }
}

onMounted(() => settings.fetchDelivery())
</script>

<style scoped>
h1 { font-family: 'Amiri', serif; color: var(--green); font-size: 1.9rem; margin-bottom: 1rem; }
</style>
