import { readLocal, writeLocal } from '~/utils/local-session'

export const REFERRAL_KEY = 'ayakun_ref'
const CODE_RE = /^[A-Za-z0-9]{4,16}$/

export const rememberReferral = (raw: unknown) => {
  const code = typeof raw === 'string' ? raw.trim() : ''
  if (CODE_RE.test(code)) writeLocal(REFERRAL_KEY, code.toUpperCase())
}

export const pendingReferral = () => readLocal(REFERRAL_KEY)

export const forgetReferral = () => writeLocal(REFERRAL_KEY, null)
