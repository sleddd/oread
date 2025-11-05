/**
 * Session Manager - Handles multiple chatbot instances for different sessions
 * Provides session-based conversation isolation
 */
import { HybridChatbot } from './chatbotHybrid.js';

const logger = console;

class SessionManager {
    constructor() {
        // Map of sessionId -> chatbot instance
        this.sessions = new Map();

        // Map of sessionId -> character name
        this.sessionCharacters = new Map();

        // Map of sessionId -> latest request ID (for race condition detection)
        this.latestRequestIds = new Map();

        // Track which characters have shown starters (global across all sessions)
        this.charactersWithStarters = new Set();

        // Session timeout: 30 minutes of inactivity
        this.sessionTimeout = 30 * 60 * 1000;

        // Track last activity for each session
        this.lastActivity = new Map();

        // Start cleanup interval (every 5 minutes)
        this.startCleanupInterval();
    }

    /**
     * Get or create a chatbot instance for a session with optional character
     */
    async getChatbot(sessionId, characterName = null, encryptionKey = null) {
        if (!sessionId) {
            throw new Error('Session ID is required');
        }

        // Update last activity
        this.lastActivity.set(sessionId, Date.now());

        // Check if we need to switch character for existing session
        if (this.sessions.has(sessionId)) {
            const chatbot = this.sessions.get(sessionId);
            const currentCharacter = this.sessionCharacters.get(sessionId);

            // Set encryption key on character loader
            if (encryptionKey) {
                chatbot.characterLoader.setEncryptionKey(encryptionKey);
            }

            // If character is specified and different, reload AND clear history
            if (characterName && characterName !== currentCharacter) {
                // Load the new character
                await chatbot.characterLoader.loadCharacterAsync(characterName);
                this.sessionCharacters.set(sessionId, characterName);

                // CRITICAL: Clear cached character to force reload with new character
                chatbot.cachedCharacter = null;
                chatbot.clearHistory();

                // Verify the new character was loaded
                const loadedName = chatbot.getActiveCharacterName();

                // Check for mismatch
                if (loadedName !== characterName) {
                    logger.error(`Character mismatch during switch`);
                }
            }

            return chatbot;
        }

        // Create new chatbot instance for this session
        const chatbot = new HybridChatbot();

        // Set encryption key on character loader
        if (encryptionKey) {
            chatbot.characterLoader.setEncryptionKey(encryptionKey);
        } else {
            logger.warn(`No encryption key - encrypted profiles will fail to load`);
        }

        // Load the specific character FIRST, before initializing
        if (characterName) {
            await chatbot.characterLoader.loadCharacterAsync(characterName);
            this.sessionCharacters.set(sessionId, characterName);

            // Verify what was actually loaded
            const loadedName = chatbot.getActiveCharacterName();

            if (loadedName !== characterName) {
                logger.error(`Character mismatch during load`);
            }
        } else {
            await chatbot.characterLoader.loadCharacterAsync();
            const loadedCharacter = chatbot.getActiveCharacterName();
            this.sessionCharacters.set(sessionId, loadedCharacter);
        }

        // Now initialize the chatbot (which will skip character loading since it's already loaded)
        await chatbot.initialize();

        this.sessions.set(sessionId, chatbot);

        return chatbot;
    }

    /**
     * Set active character for a specific session only
     */
    /**
     * Track request ID to detect race conditions
     * Returns true if this is the latest request, false if it's stale
     */
    trackRequestId(sessionId, requestId) {
        if (!requestId) {
            return true; // No tracking if no request ID provided
        }

        const currentLatest = this.latestRequestIds.get(sessionId);

        // Update to this request ID
        this.latestRequestIds.set(sessionId, requestId);

        // Detect out-of-order requests (no logging to reduce noise)

        return true; // Always process on backend (frontend will filter)
    }

    async setActiveCharacterForSession(sessionId, characterName) {
        const chatbot = this.sessions.get(sessionId);
        if (!chatbot) {
            throw new Error(`Session ${sessionId} not found`);
        }

        await chatbot.characterLoader.loadCharacterAsync(characterName);
        this.sessionCharacters.set(sessionId, characterName);

        // CRITICAL: Clear cached character to force reload with new character
        chatbot.cachedCharacter = null;
        chatbot.clearHistory();
    }

    /**
     * Clear conversation history for a session
     */
    clearSession(sessionId) {
        const chatbot = this.sessions.get(sessionId);
        if (chatbot) {
            chatbot.clearHistory();
            this.lastActivity.set(sessionId, Date.now());
        }
    }

    /**
     * Delete a session and its chatbot instance
     */
    deleteSession(sessionId) {
        if (this.sessions.has(sessionId)) {
            this.sessions.delete(sessionId);
            this.lastActivity.delete(sessionId);
        }
    }

    /**
     * Reload character for a specific session
     */
    async reloadCharacterForSession(sessionId) {
        const chatbot = this.sessions.get(sessionId);
        if (chatbot) {
            await chatbot.reloadCharacter();
            chatbot.clearHistory(); // Clear history when switching characters
            this.lastActivity.set(sessionId, Date.now());
        }
    }

    /**
     * Reload character for ALL sessions
     */
    async reloadCharacterForAllSessions() {
        const promises = [];
        for (const [sessionId, chatbot] of this.sessions.entries()) {
            promises.push(
                chatbot.reloadCharacter().then(() => {
                    chatbot.clearHistory(); // Clear history when switching characters
                    this.lastActivity.set(sessionId, Date.now());
                })
            );
        }
        await Promise.all(promises);
    }

    /**
     * Start periodic cleanup of inactive sessions
     */
    startCleanupInterval() {
        setInterval(() => {
            this.cleanupInactiveSessions();
        }, 5 * 60 * 1000); // Every 5 minutes
    }

    /**
     * Remove sessions that have been inactive for too long
     */
    cleanupInactiveSessions() {
        const now = Date.now();
        const sessionsToDelete = [];

        for (const [sessionId, lastActive] of this.lastActivity.entries()) {
            if (now - lastActive > this.sessionTimeout) {
                sessionsToDelete.push(sessionId);
            }
        }

        if (sessionsToDelete.length > 0) {
            for (const sessionId of sessionsToDelete) {
                this.deleteSession(sessionId);
            }
        }
    }

    /**
     * Check if a character needs a starter (hasn't shown one yet)
     */
    needsStarter(characterName) {
        return !this.charactersWithStarters.has(characterName);
    }

    /**
     * Mark a character as having shown a starter
     */
    markStarterShown(characterName) {
        this.charactersWithStarters.add(characterName);
    }

    /**
     * Clear starter tracking for all characters
     * Used on logout to ensure starters show on next login
     */
    clearAllStarterTracking() {
        this.charactersWithStarters.clear();
    }

    /**
     * Get stats about active sessions
     */
    getStats() {
        return {
            activeSessions: this.sessions.size,
            sessions: Array.from(this.sessions.keys())
        };
    }
}

// Singleton instance
let sessionManagerInstance = null;

export function getSessionManager() {
    if (!sessionManagerInstance) {
        sessionManagerInstance = new SessionManager();
    }
    return sessionManagerInstance;
}

export function resetSessionManager() {
    sessionManagerInstance = null;
}
