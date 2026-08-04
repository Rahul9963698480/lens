import { toast } from 'sonner';

export type NotifyPayload =
  | string
  | {
      title?: string;
      description?: string;
    };

export const notify = {
  success(payload: NotifyPayload) {
    if (typeof payload === 'string') {
      toast.success(payload);
      return;
    }
    toast.success(payload.title ?? 'Success', {
      description: payload.description,
    });
  },
  error(payload: NotifyPayload) {
    if (typeof payload === 'string') {
      toast.error(payload);
      return;
    }
    toast.error(payload.title ?? 'Error', {
      description: payload.description,
    });
  },
};
