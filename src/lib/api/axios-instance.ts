import axios from 'axios';
import { config } from '@/config/env';
import { apiErrorMessage } from '@/lib/api/error-message';
import { notify } from '@/lib/notify';

// TODO: Enable when login is implemented
// import { getAccessToken, redirectToAuth } from '@/lib/utils/auth';
// import authApi from './auth';

declare module 'axios' {
  export interface AxiosRequestConfig {
    skipErrorToast?: boolean;
  }
}

const axiosInstance = axios.create({
  baseURL: config.apiUrl,
  timeout: 30000,
  withCredentials: true,
});

// TODO: Enable token refresh queue when auth is implemented
// let isRefreshing = false;
// let failedQueue: Array<{
//   resolve: (value?: unknown) => void;
//   reject: (reason?: unknown) => void;
// }> = [];
//
// const processQueue = (error: unknown, token: string | null = null) => {
//   failedQueue.forEach(({ resolve, reject }) => {
//     if (error) reject(error);
//     else resolve(token);
//   });
//   failedQueue = [];
// };

axiosInstance.interceptors.request.use(
  (requestConfig) => {
    // TODO: Attach bearer token when auth is ready
    // const token = getAccessToken();
    // if (token) {
    //   requestConfig.headers.Authorization = `Bearer ${token}`;
    // }
    if (!(requestConfig.data instanceof FormData)) {
      requestConfig.headers['Content-Type'] = 'application/json';
    }
    if (import.meta.env.DEV) {
      console.log(
        'API Request:',
        `${requestConfig.baseURL ?? ''}${requestConfig.url ?? ''}`,
      );
    }
    return requestConfig;
  },
  (error) => Promise.reject(error),
);

axiosInstance.interceptors.response.use(
  (response) => response.data,
  async (error) => {
    const originalRequest = error.config;

    // TODO: Enable 401 refresh flow when auth is ready
    // const requestUrl: string = originalRequest?.url || '';
    // const isAuthEndpoint =
    //   requestUrl.includes('/auth/login') ||
    //   requestUrl.includes('/auth/register') ||
    //   requestUrl.includes('/auth/refresh-token') ||
    //   requestUrl.includes('/auth/logout');
    //
    // if (
    //   error.response?.status === 401 &&
    //   !originalRequest._retry &&
    //   !isAuthEndpoint
    // ) {
    //   if (isRefreshing) {
    //     return new Promise((resolve, reject) => {
    //       failedQueue.push({ resolve, reject });
    //     }).then(() => axiosInstance(originalRequest));
    //   }
    //
    //   originalRequest._retry = true;
    //   isRefreshing = true;
    //
    //   try {
    //     await authApi.refreshToken();
    //     processQueue(null, null);
    //     return axiosInstance(originalRequest);
    //   } catch (refreshError) {
    //     processQueue(refreshError, null);
    //     redirectToAuth();
    //     return Promise.reject(refreshError);
    //   } finally {
    //     isRefreshing = false;
    //   }
    // }

    const message = apiErrorMessage(
      error.response?.data,
      error.message || 'An error occurred',
    );
    const skipToast = Boolean(originalRequest?.skipErrorToast);
    if (!skipToast && error.response?.status !== 404) {
      notify.error({ title: 'Error', description: message });
    }
    return Promise.reject(error);
  },
);

export default axiosInstance;
