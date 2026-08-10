const getApiBaseUrl = (): string => {
  const envUrl = import.meta.env.VITE_API_URL;
  if (typeof envUrl === 'string' && envUrl.trim() !== '') {
    return envUrl.replace(/\/$/, '');
  }
  // Fallback: Vite dev proxy when VITE_API_URL is not set.
  if (import.meta.env.DEV) {
    return '';
  }  if (import.meta.env.MODE === 'production' && typeof window !== 'undefined') {
    const protocol = window.location.protocol;
    const host = window.location.hostname;
    const port = window.location.port ? `:${window.location.port}` : '';
    return `${protocol}//${host}${port}`;
  }
  return '';
};
export const config = {
  apiUrl: getApiBaseUrl(),
  isDevelopment: import.meta.env.MODE === 'development',
};
