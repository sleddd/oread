/**
 * Profile storage service
 * Handles all file I/O operations for profiles, user settings, and avatars
 */
import { promises as fs } from 'fs';
import path from 'path';
import { envConfig } from '../core/env_config.js';
import { EncryptionService } from '../utils/encryption.js';

// Default SVG avatar for echo profile
const DEFAULT_ECHO_AVATAR = `data:image/svg+xml;base64,${Buffer.from(`<svg version="1.2" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1016 975" width="1016" height="975">
    <style>
        .s0 { fill: #222222 }
        .s1 { fill: #1bafae }
    </style>
    <path id="Layer 1" fill-rule="evenodd" class="s0" d="m508.5 903c-223.69 0-404.5-178.8-404.5-400 0-221.2 180.81-400 404.5-400 223.69 0 404.5 178.8 404.5 400 0 221.2-180.81 400-404.5 400z"/>
    <path id="Shape 1" fill-rule="evenodd" class="s1" d="m505.12 894.84c-182.56 0-330.12-141.89-330.12-317.42 0-175.53 147.56-317.42 330.12-317.42 182.55 0 330.11 141.89 330.11 317.42 0 175.53-147.56 317.42-330.11 317.42z"/>
</svg>`).toString('base64')}`;

const DEFAULT_USER_DATA = {
    version: '2.0',
    type: 'user',
    user: {
        name: 'User',
        gender: 'non-binary',
        species: 'human',
        timezone: 'UTC',
        backstory: '',
        preferences: { music: [], books: [], movies: [], hobbies: [], other: '' },
        majorLifeEvents: [],
        communicationBoundaries: ''  // User's personal communication boundaries/preferences
    },
    settings: {},
    sharedMemory: {
        roleplayEvents: []
    }
};

// Profiles that should NEVER be encrypted (public/default characters)
const PUBLIC_PROFILES = ['Echo', 'Kairos'];

export class ProfileStorage {
    constructor() {
        this.profilesDir = envConfig.paths.profilesDir;
        this.uploadsDir = path.join(this.profilesDir, '../uploads/avatars');
    }

    /**
     * Check if a profile should be encrypted
     */
    shouldEncryptProfile(profileName) {
        return !PUBLIC_PROFILES.includes(profileName);
    }

    /**
     * Read and decrypt file content if needed
     */
    async readFileContent(filePath, encryptionKey = null) {
        let content = await fs.readFile(filePath, 'utf-8');

        // Try to decrypt if key provided and content appears encrypted
        if (encryptionKey && EncryptionService.isEncrypted(content)) {
            try {
                content = EncryptionService.decrypt(content, encryptionKey);
            } catch (err) {
                console.error('Decryption failed:', err.message);
                throw new Error('Failed to decrypt file - incorrect password or corrupted data');
            }
        }

        return content;
    }

    /**
     * Write and optionally encrypt file content
     */
    async writeFileContent(filePath, content, encryptionKey = null, shouldEncrypt = true) {
        let outputContent = content;

        // Encrypt if key provided and encryption is enabled for this file
        if (encryptionKey && shouldEncrypt) {
            outputContent = EncryptionService.encrypt(content, encryptionKey);
        }

        await fs.writeFile(filePath, outputContent, 'utf-8');
    }

    /**
     * List all profile names
     */
    async listProfiles() {
        const files = await fs.readdir(this.profilesDir);
        const profileNames = new Set();

        files.forEach(f => {
            if (f.endsWith('.json') && f !== 'user-profile.json') {
                profileNames.add(f.replace('.json', ''));
            } else if (f.endsWith('.txt') &&
                       f !== 'active-character.txt' &&
                       f !== 'user-settings.txt' &&
                       !f.endsWith('_avatar.txt')) {
                profileNames.add(f.replace('.txt', ''));
            }
        });

        return Array.from(profileNames);
    }

    /**
     * Get active profile name
     */
    async getActiveProfile(encryptionKey = null) {
        const jsonFile = path.join(this.profilesDir, 'user-profile.json');
        const txtFile = path.join(this.profilesDir, 'active-character.txt');

        // Try JSON format first (user-profile.json is always encrypted if key exists)
        try {
            const content = await this.readFileContent(jsonFile, encryptionKey);
            const data = JSON.parse(content);
            if (data.version === '2.0' && data.settings?.defaultActiveCharacter) {
                return data.settings.defaultActiveCharacter;
            }
        } catch (err) {
            // Fallback to TXT format
        }

        // Try TXT format
        try {
            const activeName = await fs.readFile(txtFile, 'utf-8');
            return activeName.trim();
        } catch (err) {
            return null;
        }
    }

    /**
     * Set active profile
     */
    async setActiveProfile(profileName, encryptionKey = null) {
        const userProfilePath = path.join(this.profilesDir, 'user-profile.json');

        try {
            // Try to load existing profile (decrypt if needed)
            const content = await this.readFileContent(userProfilePath, encryptionKey);
            const data = JSON.parse(content);

            if (!data.settings) {
                data.settings = {};
            }
            data.settings.defaultActiveCharacter = profileName;

            // Write back with encryption (user-profile.json is always encrypted if key exists)
            await this.writeFileContent(
                userProfilePath,
                JSON.stringify(data, null, 2),
                encryptionKey,
                true  // Always encrypt user-profile.json if key is provided
            );
        } catch (err) {
            // Create new profile with default data if file doesn't exist
            console.warn('[ProfileStorage] Could not read user profile, creating new one');
            console.warn('[ProfileStorage] Error:', err.message);
            const newData = { ...DEFAULT_USER_DATA };
            newData.settings.defaultActiveCharacter = profileName;

            await this.writeFileContent(
                userProfilePath,
                JSON.stringify(newData, null, 2),
                encryptionKey,
                true  // Always encrypt user-profile.json if key is provided
            );
        }
    }

    /**
     * Check if profile exists
     */
    async profileExists(profileName) {
        const jsonPath = path.join(this.profilesDir, `${profileName}.json`);
        const txtPath = path.join(this.profilesDir, `${profileName}.txt`);

        try {
            await fs.access(jsonPath);
            return true;
        } catch {
            try {
                await fs.access(txtPath);
                return true;
            } catch {
                return false;
            }
        }
    }

    /**
     * Get profile data
     */
    async getProfile(profileName, encryptionKey = null) {
        const jsonPath = path.join(this.profilesDir, `${profileName}.json`);
        const txtPath = path.join(this.profilesDir, `${profileName}.txt`);

        // Determine if we should try to decrypt this profile
        const needsDecryption = this.shouldEncryptProfile(profileName);

        // Try JSON format first
        try {
            const content = await this.readFileContent(
                jsonPath,
                needsDecryption ? encryptionKey : null
            );

            const data = JSON.parse(content);

            if (data.version === '2.0' && data.type === 'character') {
                // Return full data structure so callers can check version/type
                return data;
            }
        } catch (err) {
            console.error(`[ProfileStorage] Failed to load JSON profile: ${err.message}`);
            // Fall through to TXT
        }

        // Try TXT format (legacy) - check if file exists first
        try {
            await fs.access(txtPath);
        } catch (accessErr) {
            // TXT file doesn't exist either - throw the original JSON error
            throw new Error(`Profile not found or cannot be decrypted`);
        }

        const content = await fs.readFile(txtPath, 'utf-8');
        const lines = content.split('\n');
        const profile = {};

        for (const line of lines) {
            if (line.includes('=')) {
                const firstEquals = line.indexOf('=');
                const key = line.substring(0, firstEquals).trim();
                const value = line.substring(firstEquals + 1).replace(/\\n/g, '\n');
                profile[key] = (key === 'notifications') ? value === 'true' : value;
            }
        }

        return profile;
    }

    /**
     * Save profile data
     */
    async saveProfile(profileName, profileData, encryptionKey = null) {
        const jsonPath = path.join(this.profilesDir, `${profileName}.json`);

        // Check if profileData is already a full v2.0 structure (e.g., during re-encryption)
        let data;
        if (profileData.version === '2.0' && profileData.type === 'character') {
            // Already in full format - preserve it exactly as-is
            data = profileData;
        } else {
            // Legacy format or flat character object - build v2.0 structure
            // BUT: Load existing profile first to preserve favorites and other metadata
            let existingData = null;
            const needsDecryption = this.shouldEncryptProfile(profileName);

            try {
                const content = await this.readFileContent(
                    jsonPath,
                    needsDecryption ? encryptionKey : null
                );
                existingData = JSON.parse(content);
            } catch (err) {
                // Profile doesn't exist yet or can't be read - will create new one
            }

            // Merge with existing data to preserve favorites
            data = {
                version: '2.0',
                type: 'character',
                character: {
                    name: profileData.name || profileName,
                    gender: profileData.gender || 'female',
                    species: profileData.species || 'human',
                    age: parseInt(profileData.age) || 25,
                    role: profileData.role || '',
                    companionType: profileData.companionType || 'friend',
                    appearance: profileData.appearance || '',
                    traits: profileData.traits || '',
                    interests: profileData.interests || '',
                    backstory: profileData.backstory || '',
                    boundaries: profileData.boundaries || '',
                    avoidWords: profileData.avoidWords || '',
                    notifications: profileData.notifications !== false,
                    tagSelections: profileData.tagSelections || {},
                    // CRITICAL: Preserve favorites from existing profile or incoming data
                    favorites: profileData.favorites || (existingData?.character?.favorites) || []
                }
            };
        }

        const jsonContent = JSON.stringify(data, null, 2);
        const shouldEncrypt = this.shouldEncryptProfile(profileName);

        await this.writeFileContent(jsonPath, jsonContent, encryptionKey, shouldEncrypt);
    }

    /**
     * Delete profile
     */
    async deleteProfile(profileName) {
        const jsonPath = path.join(this.profilesDir, `${profileName}.json`);
        const txtPath = path.join(this.profilesDir, `${profileName}.txt`);
        const avatarPath = path.join(this.profilesDir, `${profileName}_avatar.txt`);

        // Delete profile files (try both formats)
        await Promise.allSettled([
            fs.unlink(jsonPath),
            fs.unlink(txtPath),
            fs.unlink(avatarPath)
        ]);

        // Delete avatar image (new format)
        try {
            const files = await fs.readdir(this.uploadsDir);
            const avatarFile = files.find(f => f.startsWith(profileName + '.'));
            if (avatarFile) {
                await fs.unlink(path.join(this.uploadsDir, avatarFile));
            }
        } catch (err) {
            // Ignore if uploads dir doesn't exist
        }
    }

    /**
     * Get user settings
     */
    async getUserSettings(encryptionKey = null) {
        const jsonFile = path.join(this.profilesDir, 'user-profile.json');
        const txtFile = path.join(this.profilesDir, 'user-settings.txt');

        // Try JSON format first (user-profile.json is always encrypted if key exists)
        try {
            const content = await this.readFileContent(jsonFile, encryptionKey);
            const data = JSON.parse(content);

            if (data.version === '2.0' && data.type === 'user') {
                // Return full data structure so callers can access all fields
                return data;
            }
        } catch (err) {
            // This is expected if file is encrypted and no key provided
            if (err.message.includes('not valid JSON') || err.message.includes('Unexpected token')) {
                console.log('[ProfileStorage] User settings encrypted - will load after login');
            } else {
                console.error('[ProfileStorage] Error loading user settings JSON:', err.message);
            }
            // Fall through to TXT
        }

        // Try TXT format (legacy)
        try {
            const content = await fs.readFile(txtFile, 'utf-8');
            const lines = content.split('\n');
            const settings = {
                userName: 'User',
                userGender: 'non-binary',
                userSpecies: 'human',
                timezone: 'UTC',
                userBackstory: '',
                userPreferences: { music: [], books: [], movies: [], hobbies: [], other: '' },
                majorLifeEvents: [],
                sharedRoleplayEvents: []
            };

            for (const line of lines) {
                if (line.includes('=')) {
                    const firstEquals = line.indexOf('=');
                    const key = line.substring(0, firstEquals).trim();
                    const value = line.substring(firstEquals + 1);
                    if (key in settings) {
                        settings[key] = value;
                    }
                }
            }

            return settings;
        } catch (err) {
            // Return defaults
            return {
                userName: 'User',
                userGender: 'non-binary',
                userSpecies: 'human',
                timezone: 'UTC',
                userBackstory: '',
                userPreferences: { music: [], books: [], movies: [], hobbies: [], other: '' },
                majorLifeEvents: [],
                sharedRoleplayEvents: []
            };
        }
    }

    /**
     * Save user settings
     */
    async saveUserSettings(settings, encryptionKey = null) {
        const jsonFile = path.join(this.profilesDir, 'user-profile.json');

        // Load existing data to preserve other fields
        let existingData = DEFAULT_USER_DATA;
        try {
            const content = await this.readFileContent(jsonFile, encryptionKey);
            existingData = JSON.parse(content);
        } catch (err) {
            // Check if file exists - if it does but we can't read it, that's a problem
            try {
                await fs.access(jsonFile);
                // File exists but can't be read - likely encryption key issue
                // DO NOT overwrite with defaults!
                console.error('[ProfileStorage] CRITICAL: user profile exists but cannot be read!');
                console.error('[ProfileStorage] Refusing to overwrite with defaults');
                throw new Error('Cannot save user settings - unable to read existing profile (encryption key mismatch?)');
            } catch (accessErr) {
                // File doesn't exist - safe to use defaults
            }
        }

        // Update user section
        existingData.user = {
            name: settings.userName || 'User',
            gender: settings.userGender || 'non-binary',
            species: settings.userSpecies || 'human',
            timezone: settings.timezone || 'UTC',
            backstory: settings.userBackstory || '',
            preferences: settings.userPreferences || { music: [], books: [], movies: [], hobbies: [], other: '' },
            majorLifeEvents: settings.majorLifeEvents || [],
            communicationBoundaries: settings.communicationBoundaries || ''
        };

        existingData.sharedMemory = {
            roleplayEvents: settings.sharedRoleplayEvents || []
        };

        // Update settings section with advanced features (preserve existing settings)
        if (!existingData.settings) {
            existingData.settings = {};
        }
        existingData.settings.enableMemory = settings.enableMemory !== undefined ? settings.enableMemory : false;
        existingData.settings.enableWebSearch = settings.enableWebSearch !== undefined ? settings.enableWebSearch : false;
        existingData.settings.webSearchApiKey = settings.webSearchApiKey || '';

        // Update defaultActiveCharacter if provided
        if (settings.defaultActiveCharacter !== undefined) {
            existingData.settings.defaultActiveCharacter = settings.defaultActiveCharacter;
        }

        // Preserve consent data if it exists (it's already in existingData)

        const jsonContent = JSON.stringify(existingData, null, 2);
        await this.writeFileContent(jsonFile, jsonContent, encryptionKey, true); // Always encrypt user-profile
    }

    /**
     * Get avatar for profile
     */
    async getAvatar(profileName) {
        // Check for image files in uploads directory
        try {
            const files = await fs.readdir(this.uploadsDir);
            const avatarFile = files.find(f => f.startsWith(profileName + '.'));
            if (avatarFile) {
                // Return URL path (not filesystem path) - Express serves /uploads from data/uploads
                const avatarPath = `/uploads/avatars/${avatarFile}`;
                return avatarPath;
            }
        } catch (err) {
            // Ignore error
        }

        // Check old format (_avatar.txt)
        try {
            const oldAvatarPath = path.join(this.profilesDir, `${profileName}_avatar.txt`);
            const avatarData = await fs.readFile(oldAvatarPath, 'utf-8');
            return avatarData;
        } catch (err) {
            // Ignore error
        }

        // Return default for echo
        if (profileName.toLowerCase() === 'echo') {
            return DEFAULT_ECHO_AVATAR;
        }

        return null;
    }

    /**
     * Get consent data
     * NOTE: This needs to work both before login (unencrypted) and after login (encrypted)
     */
    async getConsent(encryptionKey = null) {
        const jsonFile = path.join(this.profilesDir, 'user-profile.json');

        try {
            // Try encrypted read first (will work both for encrypted and unencrypted)
            const content = await this.readFileContent(jsonFile, encryptionKey);
            const data = JSON.parse(content);

            if (data.consent) {
                return data.consent;
            }
        } catch (err) {
            // Silent - consent may not exist yet
        }

        // Return default
        return {
            accepted: false,
            timestamp: null,
            version: '1.0',
            checkboxes: {
                ageConfirmation: false,
                fictionalityAcknowledgment: false,
                prohibitedActivities: false,
                realPersonLikeness: false,
                aiLimitations: false,
                narrativeConsent: false,
                experimentalRisks: false,
                termsOfService: false
            }
        };
    }

    /**
     * Save consent data
     * NOTE: Consent is usually saved BEFORE login (unencrypted), but we need to handle
     * updates after login (encrypted) as well
     */
    async saveConsent(consentData, encryptionKey = null) {
        const jsonFile = path.join(this.profilesDir, 'user-profile.json');

        // Load existing data
        let existingData = DEFAULT_USER_DATA;
        try {
            // Try to read with encryption support
            const content = await this.readFileContent(jsonFile, encryptionKey);
            existingData = JSON.parse(content);
        } catch (err) {
            // Use defaults if file doesn't exist
        }

        existingData.consent = consentData;

        // Write with encryption if key is available (after login)
        // Write unencrypted if no key (before login)
        await this.writeFileContent(
            jsonFile,
            JSON.stringify(existingData, null, 2),
            encryptionKey,
            !!encryptionKey  // Encrypt if key is provided
        );
    }

    /**
     * Get favorites for a character
     */
    async getFavorites(profileName, encryptionKey = null) {
        const jsonPath = path.join(this.profilesDir, `${profileName}.json`);
        const needsDecryption = this.shouldEncryptProfile(profileName);

        try {
            const content = await this.readFileContent(
                jsonPath,
                needsDecryption ? encryptionKey : null
            );
            const data = JSON.parse(content);

            if (data.version === '2.0' && data.type === 'character') {
                return data.character.favorites || [];
            }
        } catch (err) {
            console.error(`Error getting favorites for ${profileName}:`, err);
        }

        return [];
    }

    /**
     * Add a favorite to a character
     */
    async addFavorite(profileName, favorite, encryptionKey = null) {
        const jsonPath = path.join(this.profilesDir, `${profileName}.json`);
        const needsEncryption = this.shouldEncryptProfile(profileName);

        try {
            const content = await this.readFileContent(
                jsonPath,
                needsEncryption ? encryptionKey : null
            );
            const data = JSON.parse(content);

            if (data.version === '2.0' && data.type === 'character') {
                if (!data.character.favorites) {
                    data.character.favorites = [];
                }

                // Add the favorite with a unique ID
                const favoriteWithId = {
                    id: favorite.id || `fav-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
                    text: favorite.text,
                    senderName: favorite.senderName || 'Unknown',
                    timestamp: favorite.timestamp || new Date().toISOString(),
                    emotion: favorite.emotion || null,
                    sentiment: favorite.sentiment || null
                };

                data.character.favorites.push(favoriteWithId);

                const jsonContent = JSON.stringify(data, null, 2);
                await this.writeFileContent(jsonPath, jsonContent, encryptionKey, needsEncryption);

                return favoriteWithId;
            }
        } catch (err) {
            console.error(`Error adding favorite to ${profileName}:`, err);
            throw err;
        }

        throw new Error(`Profile ${profileName} not found or invalid format`);
    }

    /**
     * Remove a favorite from a character
     */
    async removeFavorite(profileName, favoriteId, encryptionKey = null) {
        const jsonPath = path.join(this.profilesDir, `${profileName}.json`);
        const needsEncryption = this.shouldEncryptProfile(profileName);

        try {
            const content = await this.readFileContent(
                jsonPath,
                needsEncryption ? encryptionKey : null
            );
            const data = JSON.parse(content);

            if (data.version === '2.0' && data.type === 'character') {
                if (!data.character.favorites) {
                    data.character.favorites = [];
                }

                const initialLength = data.character.favorites.length;
                data.character.favorites = data.character.favorites.filter(fav => fav.id !== favoriteId);

                if (data.character.favorites.length === initialLength) {
                    throw new Error(`Favorite ${favoriteId} not found`);
                }

                const jsonContent = JSON.stringify(data, null, 2);
                await this.writeFileContent(jsonPath, jsonContent, encryptionKey, needsEncryption);
                return true;
            }
        } catch (err) {
            console.error(`Error removing favorite from ${profileName}:`, err);
            throw err;
        }

        throw new Error(`Profile ${profileName} not found or invalid format`);
    }

    /**
     * Re-encrypt all data with new password (for password changes)
     */
    async reEncryptAllData(oldPassword, newPassword) {
        console.log('Re-encrypting all profile data with new password...');

        const profiles = await this.listProfiles();

        for (const profileName of profiles) {
            if (!this.shouldEncryptProfile(profileName)) {
                continue;
            }

            try {
                const jsonPath = path.join(this.profilesDir, `${profileName}.json`);

                // Try old password first
                let profileContent;
                let alreadyReEncrypted = false;

                try {
                    profileContent = await this.readFileContent(jsonPath, oldPassword);
                } catch (oldPasswordErr) {
                    // Maybe it's already re-encrypted with new password?
                    try {
                        profileContent = await this.readFileContent(jsonPath, newPassword);
                        alreadyReEncrypted = true;
                    } catch (newPasswordErr) {
                        throw new Error(`Cannot decrypt profile - may be corrupted`);
                    }
                }

                // Only re-encrypt if not already done
                if (!alreadyReEncrypted) {
                    const profileData = JSON.parse(profileContent);
                    await this.saveProfile(profileName, profileData, newPassword);
                }
            } catch (err) {
                console.error(`Failed to re-encrypt profile:`, err.message);
                throw new Error(`Failed to re-encrypt profile`);
            }
        }

        // Re-encrypt user profile
        try {
            // Read the raw file directly to preserve full structure
            const jsonFile = path.join(this.profilesDir, 'user-profile.json');

            let userProfileContent;
            let alreadyReEncrypted = false;

            // Try old password first
            try {
                userProfileContent = await this.readFileContent(jsonFile, oldPassword);
            } catch (oldPasswordErr) {
                // Maybe it's already re-encrypted with new password?
                try {
                    userProfileContent = await this.readFileContent(jsonFile, newPassword);
                    alreadyReEncrypted = true;
                } catch (newPasswordErr) {
                    throw new Error('Cannot decrypt user profile - may be corrupted');
                }
            }

            // Only re-encrypt if not already done
            if (!alreadyReEncrypted) {
                const userProfileData = JSON.parse(userProfileContent);

                // Write it back with new encryption (preserve exact structure)
                const jsonContent = JSON.stringify(userProfileData, null, 2);
                await this.writeFileContent(jsonFile, jsonContent, newPassword, true);
            }
        } catch (err) {
            console.error('Failed to re-encrypt user profile:', err.message);
            throw new Error('Failed to re-encrypt user profile');
        }

        console.log('All data successfully re-encrypted');
    }
}

// Singleton instance
let storageInstance = null;

export function getProfileStorage() {
    if (!storageInstance) {
        storageInstance = new ProfileStorage();
    }
    return storageInstance;
}
