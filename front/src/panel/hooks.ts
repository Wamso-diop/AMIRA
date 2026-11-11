import { useCallback, useEffect, useRef, useState } from 'react';
import { DEFAULT_SETTINGS, loadSettings, normalizeSettings, saveSettings, SETTINGS_KEY, type Settings } from '../services/settings';
import { EMPTY_STATS, type ContentEvent, type PageStats, type StatusResult } from '../shared/messages';
import { bg, toTab } from './bridge';

export function useSettings() {
  const [settings, setSettings] = useState<Settings | null>(null);
  useEffect(() => {
    let alive = true;
    void loadSettings().then((s) => alive && setSettings(s));
    const onChange = (changes: Record<string, chrome.storage.StorageChange>, area: string) => {
      if (area === 'local' && changes[SETTINGS_KEY]) setSettings(normalizeSettings(changes[SETTINGS_KEY].newValue));
    };
    chrome.storage.onChanged.addListener(onChange);
    return () => {
      alive = false;
      chrome.storage.onChanged.removeListener(onChange);
    };
  }, []);
  const update = useCallback(async (patch: Partial<Settings>) => {
    setSettings((s) => ({ ...(s ?? DEFAULT_SETTINGS), ...patch }) as Settings);
    await saveSettings(patch);
  }, []);
  return [settings, update] as const;
}

export function useStatus(deps: unknown[]) {
  const [status, setStatus] = useState<StatusResult | null>(null);
  const [checking, setChecking] = useState(false);
  const refresh = useCallback(async () => {
    setChecking(true);
    try {
      setStatus(await bg<StatusResult>({ type: 'amira:status' }));
    } catch {
      setStatus({ state: 'error', demo: false, capabilities: null, errorCode: 'CLIENT_ERROR' });
    } finally {
      setChecking(false);
    }
  }, []);
  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { status, checking, refresh };
}

/** Statistiques de la page active, agrégées sur toutes les frames de l'onglet. */
export function usePageStats() {
  const [stats, setStats] = useState<PageStats>(EMPTY_STATS);
  const [reachable, setReachable] = useState<boolean | null>(null);
  const frames = useRef(new Map<number, PageStats>());
  const tabId = useRef<number | undefined>(undefined);

  const aggregate = useCallback(() => {
    const all = [...frames.current.values()];
    const top = frames.current.get(0) ?? all[0] ?? EMPTY_STATS;
    setStats({
      ...top,
      translated: all.reduce((n, s) => n + s.translated, 0),
      kept: all.reduce((n, s) => n + s.kept, 0),
      errors: all.reduce((n, s) => n + s.errors, 0),
      pending: all.reduce((n, s) => n + s.pending, 0),
      total: all.reduce((n, s) => n + s.total, 0),
    });
  }, []);

  const refresh = useCallback(async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab?.id !== tabId.current) frames.current.clear();
    tabId.current = tab?.id;
    try {
      const s = await toTab({ type: 'amira:getStats' });
      frames.current.set(0, s);
      setReachable(true);
      aggregate();
    } catch {
      frames.current.clear();
      setReachable(false);
      setStats(EMPTY_STATS);
    }
  }, [aggregate]);

  useEffect(() => {
    void refresh();
    const onMsg = (msg: ContentEvent, sender: chrome.runtime.MessageSender) => {
      if (msg?.type !== 'amira:stats' || sender.tab?.id !== tabId.current) return;
      frames.current.set(sender.frameId ?? 0, msg.stats);
      setReachable(true);
      aggregate();
    };
    chrome.runtime.onMessage.addListener(onMsg);
    // traduction pas encore activée : le moteur n'observe pas la page, on relit la langue régulièrement
    const poll = setInterval(() => {
      const top = frames.current.get(0);
      if (top && !top.enabled && document.visibilityState === 'visible') void refresh();
    }, 3000);
    const onActivated = () => void refresh();
    chrome.tabs.onActivated?.addListener(onActivated);
    chrome.tabs.onUpdated?.addListener(onActivated);
    return () => {
      clearInterval(poll);
      chrome.runtime.onMessage.removeListener(onMsg);
      chrome.tabs.onActivated?.removeListener(onActivated);
      chrome.tabs.onUpdated?.removeListener(onActivated);
    };
  }, [aggregate, refresh]);

  return { stats, setStats, reachable, refresh };
}
