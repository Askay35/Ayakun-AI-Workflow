import { readLocal, writeLocal } from '~/utils/local-session'

const AFTER_LOGIN_KEY = 'ayakun_after_login'

/** Куда вернуть пользователя после входа: например, к копированию шаблона. */
export const rememberAfterLogin = (path: string) => {
  if (path.startsWith('/') && !path.startsWith('//') && !path.startsWith('/login')) writeLocal(AFTER_LOGIN_KEY, path)
}

export const takeAfterLogin = (fallback = '/dashboard') => {
  const path = readLocal(AFTER_LOGIN_KEY)
  writeLocal(AFTER_LOGIN_KEY, null)
  return path && path.startsWith('/') && !path.startsWith('//') ? path : fallback
}
