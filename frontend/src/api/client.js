import axios from 'axios'

export const API_BASE_URL = 'http://127.0.0.1:8000'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
})

// Automatically attach the saved token to every outgoing request, if one exists.
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export default apiClient