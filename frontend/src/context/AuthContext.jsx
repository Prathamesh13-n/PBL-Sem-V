import { createContext, useContext, useState, useEffect } from 'react'
import apiClient from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  // On first load, if a token is already saved (from a previous session),
  // try to fetch the current user so a page refresh doesn't log you out.
  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      setLoading(false)
      return
    }
    apiClient
      .get('/auth/me')
      .then((res) => setUser(res.data))
      .catch(() => localStorage.removeItem('access_token'))
      .finally(() => setLoading(false))
  }, [])

  async function login(email, password) {
    const res = await apiClient.post('/auth/login', { email, password })
    localStorage.setItem('access_token', res.data.access_token)
    const me = await apiClient.get('/auth/me')
    setUser(me.data)
    return me.data
  }

  async function register(fullName, email, password) {
    await apiClient.post('/auth/register', {
      full_name: fullName,
      email,
      password,
    })
    // Registration doesn't log you in automatically — matches the backend,
    // which only issues a token on /auth/login.
  }

  function logout() {
    localStorage.removeItem('access_token')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used inside an AuthProvider')
  }
  return context
}