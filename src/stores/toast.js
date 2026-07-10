import { defineStore } from 'pinia'

// Shared toast/notification service. Any component: toast.show('تم الحفظ')
export const useToastStore = defineStore('toast', {
  state: () => ({ message: '', _t: null }),
  actions: {
    show(message, ms = 2400) {
      this.message = message
      clearTimeout(this._t)
      this._t = setTimeout(() => { this.message = '' }, ms)
    },
  },
})
