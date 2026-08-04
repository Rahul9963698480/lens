import axiosInstance from './axios-instance';

export type HealthResponse = {
  status: string;
};

const healthApi = {
  check: () => axiosInstance.get<HealthResponse>('/health'),
};

export default healthApi;
