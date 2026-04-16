export const CHAT_ROLE_USER = 'user' as const;
export const CHAT_ROLE_AI = 'ai' as const;

export type ChatRole = typeof CHAT_ROLE_USER | typeof CHAT_ROLE_AI;
