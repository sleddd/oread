/**
 * Authentication Routes
 * Password-based authentication with bcrypt hashing
 */

import express from 'express';
import bcrypt from 'bcrypt';
import os from 'os';
import { promises as fs } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { getProfileStorage } from '../services/ProfileStorage.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const router = express.Router();

// Bcrypt configuration
const SALT_ROUNDS = 12; // Higher = more secure but slower (12 is good balance)

/**
 * POST /auth/login
 * Authenticate with password
 */
router.post('/auth/login', async (req, res) => {
    try {
        const { password } = req.body;

        if (!password) {
            return res.status(400).json({
                success: false,
                error: 'Password is required'
            });
        }

        // Get stored bcrypt hash from environment
        const storedHash = process.env.APP_PASSWORD_HASH;

        if (!storedHash) {
            console.error('❌ APP_PASSWORD_HASH not set in .env file!');
            return res.status(500).json({
                success: false,
                error: 'Authentication not configured. Please set APP_PASSWORD_HASH in .env'
            });
        }

        // Use bcrypt to compare password with stored hash
        const isValid = await bcrypt.compare(password, storedHash);

        if (isValid) {
            // Create secure session
            req.session.authenticated = true;
            req.session.loginTime = new Date().toISOString();
            // Store password for encryption/decryption (only in memory, not persisted to disk)
            req.session.encryptionKey = password;

            console.log(`✅ Authentication successful`);

            // Save session
            req.session.save((err) => {
                if (err) {
                    console.error('Session save error:', err);
                    return res.status(500).json({
                        success: false,
                        error: 'Failed to create session'
                    });
                }

                return res.json({
                    success: true,
                    message: 'Authentication successful'
                });
            });
        } else {
            console.log(`❌ Authentication failed: Invalid password`);
            return res.status(401).json({
                success: false,
                error: 'Invalid password'
            });
        }
    } catch (error) {
        console.error('Login error:', error);
        return res.status(500).json({
            success: false,
            error: 'Authentication system error'
        });
    }
});

/**
 * POST /auth/logout
 * Destroy the current session and clear chatbot state
 */
router.post('/auth/logout', async (req, res) => {
    try {
        // Get session ID before destroying session
        const sessionId = req.body.sessionId || req.headers['x-session-id'];

        // Clear chatbot session if session ID is provided
        if (sessionId) {
            try {
                const { getSessionManager } = await import('../core/sessionManager.js');
                const sessionManager = getSessionManager();

                // Delete the chatbot session (clears conversation history and instance)
                sessionManager.deleteSession(sessionId);

                // Clear starter tracking so starters show on next login
                sessionManager.clearAllStarterTracking();

                console.log(`✅ Cleared chatbot session and starter tracking`);
            } catch (sessionError) {
                console.error('Failed to clear chatbot session:', sessionError);
                // Continue with logout even if session clear fails
            }
        }

        // Destroy the auth session
        if (req.session) {
            req.session.destroy((err) => {
                if (err) {
                    console.error('Session destruction error:', err);
                    return res.status(500).json({
                        success: false,
                        error: 'Failed to logout'
                    });
                }

                // Clear the session cookie
                res.clearCookie('connect.sid');

                return res.json({
                    success: true,
                    message: 'Logged out successfully'
                });
            });
        } else {
            return res.json({
                success: true,
                message: 'No active session'
            });
        }
    } catch (error) {
        console.error('Logout error:', error);
        return res.status(500).json({
            success: false,
            error: 'Failed to logout'
        });
    }
});

/**
 * GET /auth/verify
 * Check if the current session is valid
 */
router.get('/auth/verify', (req, res) => {
    if (req.session && req.session.authenticated) {
        return res.json({
            authenticated: true,
            loginTime: req.session.loginTime
        });
    } else {
        return res.json({
            authenticated: false
        });
    }
});

/**
 * POST /auth/change-password
 * Change the application password and update .env file
 * Requires active session
 */
router.post('/auth/change-password', async (req, res) => {
    try {
        // Check if user is authenticated
        if (!req.session || !req.session.authenticated) {
            return res.status(401).json({
                success: false,
                error: 'Unauthorized'
            });
        }

        const { newPassword, confirmPassword } = req.body;

        // Validate inputs
        if (!newPassword || !confirmPassword) {
            return res.status(400).json({
                success: false,
                error: 'Both password fields are required'
            });
        }

        if (newPassword !== confirmPassword) {
            return res.status(400).json({
                success: false,
                error: 'Passwords do not match'
            });
        }

        if (newPassword.length < 12) {
            return res.status(400).json({
                success: false,
                error: 'Password must be at least 12 characters long'
            });
        }

        // Get old password from session for re-encryption
        const oldPassword = req.session.encryptionKey;

        if (!oldPassword) {
            return res.status(400).json({
                success: false,
                error: 'Session expired. Please log in again to change password'
            });
        }

        // Re-encrypt all encrypted data with new password
        try {
            const storage = getProfileStorage();
            await storage.reEncryptAllData(oldPassword, newPassword);
            console.log('✅ Data re-encrypted with new password');

            // CRITICAL: Invalidate all caches after re-encryption
            const { getProfileCache } = await import('../services/ProfileCache.js');
            const profileCache = getProfileCache();
            profileCache.invalidateUserSettings();
            profileCache.invalidateProfileList();
            console.log('✅ Cache invalidated after re-encryption');
        } catch (reEncryptError) {
            console.error('Re-encryption failed:', reEncryptError);
            return res.status(500).json({
                success: false,
                error: 'Failed to re-encrypt data with new password'
            });
        }

        // Hash the new password with bcrypt
        const newPasswordHash = await bcrypt.hash(newPassword, SALT_ROUNDS);

        // Read the .env file - use process.cwd() for more reliable path
        const envPath = path.join(process.cwd(), '.env');

        let envContent;
        try {
            envContent = await fs.readFile(envPath, 'utf-8');
        } catch (readError) {
            console.error('Failed to read .env file');
            throw new Error('Failed to update password hash in configuration file');
        }

        // Update the APP_PASSWORD_HASH value
        const envLines = envContent.split('\n');
        let updated = false;

        for (let i = 0; i < envLines.length; i++) {
            if (envLines[i].startsWith('APP_PASSWORD_HASH=')) {
                envLines[i] = `APP_PASSWORD_HASH=${newPasswordHash}`;
                updated = true;
                break;
            }
        }

        // If APP_PASSWORD_HASH doesn't exist, add it
        if (!updated) {
            envLines.push(`APP_PASSWORD_HASH=${newPasswordHash}`);
        }

        // Write back to .env file
        await fs.writeFile(envPath, envLines.join('\n'), 'utf-8');

        // Update the environment variable in the current process
        process.env.APP_PASSWORD_HASH = newPasswordHash;

        // Update session with new encryption key
        req.session.encryptionKey = newPassword;

        console.log(`✅ Password changed successfully`);

        return res.json({
            success: true,
            message: 'Password updated successfully'
        });

    } catch (error) {
        console.error('Password change error:', error);
        return res.status(500).json({
            success: false,
            error: 'Failed to update password'
        });
    }
});

export default router;