// @vitest-environment jsdom
import { afterEach, describe, expect, test, vi } from 'vitest';

const bg = vi.fn();
vi.mock('../../src/panel/bridge', () => ({ bg: (m: unknown) => bg(m) }));
const { play, stop, subscribe, IDLE } = await import('../../src/panel/player');

const speak = vi.fn();
(globalThis as any).speechSynthesis = { speak, cancel: vi.fn(), pause: vi.fn(), resume: vi.fn() };
(globalThis as any).SpeechSynthesisUtterance = class {};
const audios: { src: string; onended?: () => void }[] = [];
(globalThis as any).Audio = class {
  onended?: () => void;
  playbackRate = 1;
  constructor(public src: string) {
    audios.push(this);
  }
  play() {
    return Promise.resolve();
  }
  pause() {}
};

const none = { ok: true, data: { audioBase64: '', mimeType: 'audio/mpeg', voice: 'synthetic' } };
const rec = { ok: true, data: { audioBase64: 'AAAA', mimeType: 'audio/mp4', voice: 'recorded' } };

afterEach(() => {
  stop();
  bg.mockReset();
  speak.mockReset();
  audios.length = 0;
  vi.useRealTimers();
});

describe('lecteur', () => {
  test("sans enregistrement : message, pas de voix de synthèse, puis passage suivant", async () => {
    vi.useFakeTimers();
    bg.mockResolvedValueOnce(none).mockResolvedValueOnce(rec);
    let s = IDLE;
    const off = subscribe((x) => (s = x));
    await play([{ text: 'a', key: 'k00000001' }, { text: 'b', key: 'k00000002' }], 'ff', 1);
    expect(s.missing).toBe(true);
    expect(speak).not.toHaveBeenCalled();
    await vi.runAllTimersAsync();
    expect(bg).toHaveBeenCalledTimes(2);
    expect(audios.map((a) => a.src)).toEqual(['data:audio/mp4;base64,AAAA']);
    expect(s.missing).toBe(false);
    expect(s.voice).toBe('recorded');
    off();
  });

  test('le message reste affiché à la fin si le dernier passage n’a pas d’enregistrement', async () => {
    vi.useFakeTimers();
    bg.mockResolvedValue(none);
    let s = IDLE;
    const off = subscribe((x) => (s = x));
    await play(['a'], 'ff', 1);
    await vi.runAllTimersAsync();
    expect(s.status).toBe('idle');
    expect(s.missing).toBe(true);
    expect(speak).not.toHaveBeenCalled();
    off();
  });
});
