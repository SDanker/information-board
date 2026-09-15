import { getActiveLanguage, interpolate, Language } from "../core";
import { adminMessages } from "./admin";
import { boardMessages } from "./board";
import { commonMessages } from "./common";
import { contentMessages } from "./content";
import { playlistMessages } from "./playlists";
import { publicMessages } from "./public";
import { settingsMessages } from "./settings";

// Every message group is merged here. TypeScript rejects a Spanish group that misses or adds
// a key, and MessageKey rejects calls to t() with a key that does not exist.
const groups = [commonMessages, adminMessages, boardMessages, contentMessages, playlistMessages, publicMessages, settingsMessages] as const;

type GroupKeys<G> = G extends { en: infer E } ? keyof E : never;
export type MessageKey = GroupKeys<(typeof groups)[number]> & string;
/** Base of every "<base>.one" / "<base>.other" message pair, for count-dependent wording. */
export type PluralKey = { [K in MessageKey]: K extends `${infer Base}.one` ? Base : never }[MessageKey];

export const MESSAGES = {
  en: Object.assign({}, ...groups.map((group) => group.en)),
  es: Object.assign({}, ...groups.map((group) => group.es)),
} as Record<Language, Record<MessageKey, string>>;

export function hasMessage(key: string): key is MessageKey {
  return key in MESSAGES.en;
}

/** Translate outside React (e.g. the API client) using the currently active language. */
export function translate(key: MessageKey, vars?: Record<string, string | number>): string {
  return interpolate(MESSAGES[getActiveLanguage()][key] ?? MESSAGES.en[key] ?? key, vars);
}
