const getApiBaseUrl = (): string => {
  const envUrl = import.meta.env.VITE_API_URL;
  if (envUrl) {
    if (envUrl.startsWith('/')) {
      return envUrl.replace(/\/$/, '');
    }
    let url = envUrl.replace(/\/$/, '');
    if (!url.endsWith('/api/v1')) {
      if (url.endsWith('/api')) {
        url += '/v1';
      } else {
        url += '/api/v1';
      }
    }
    return url;
  }
  if (import.meta.env.MODE === 'production' && typeof window !== 'undefined') {
    const protocol = window.location.protocol;
    const host = window.location.hostname;
    const port = window.location.port ? `:${window.location.port}` : '';
    return `${protocol}//${host}${port}/api/v1`;
  }
  return '/api/v1';
};

export const config = {
  apiUrl: getApiBaseUrl(),
  isDevelopment: import.meta.env.MODE === 'development',
};
