/** Test stand-in for vite-plugin-pwa's `virtual:pwa-register`. */
interface Options {
  onNeedRefresh?: () => void;
}

export const registered: { options: Options | null; reloads: number } = { options: null, reloads: 0 };

export function registerSW(options: Options = {}): (reload?: boolean) => Promise<void> {
  registered.options = options;
  return () => {
    registered.reloads += 1;
    return Promise.resolve();
  };
}
