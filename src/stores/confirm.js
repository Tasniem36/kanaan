import { defineStore } from 'pinia'

// Central confirm/alert service. Any component calls:
//   const ok = await confirm.ask({ title, message, danger: true })
// A single <ConfirmDialog/> (mounted in App.vue) renders the result.
export const useConfirmStore = defineStore('confirm', {
  state: () => ({
    open: false,
    options: {},
    _resolve: null,
  }),
  actions: {
    ask(options = {}) {
      this.options = {
        title: '',
        message: '',
        confirmText: '', // ConfirmDialog falls back to a translated default
        cancelText: '',
        danger: false,
        alert: false, // when true, only an OK button (no cancel)
        ...options,
      }
      this.open = true
      return new Promise((resolve) => {
        this._resolve = resolve
      })
    },
    // convenience: a message-only acknowledgement
    alert(message, title = 'تنبيه') {
      return this.ask({ message, title, alert: true, confirmText: 'حسنًا' })
    },
    respond(value) {
      this.open = false
      const resolve = this._resolve
      this._resolve = null
      if (resolve) resolve(value)
    },
  },
})
